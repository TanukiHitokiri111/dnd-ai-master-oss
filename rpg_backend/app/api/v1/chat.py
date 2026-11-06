from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
import json as _json
from pathlib import Path
from app.models import ChatRequest, ChatResponse
from app.services.chat_service import chat_service
from app.services.rate_limiter import rate_limiter
from app.exceptions import AIError, RateLimitError
from app.logger import logger
from app.deps import get_current_user
from app.db import get_db

router = APIRouter(prefix="/chat", tags=["Chat"])

# Директория сгенерированных сцен (writable volume ./data:/app/data)
_SCENES_DIR = Path("/app/data/scenes")
_APPEARANCE_DIR = Path("/app/data/appearance")


@router.get("/scenes/{filename}")
async def get_scene_image(filename: str):
    """Отдать сгенерированную картинку сцены."""
    if not filename or "\\" in filename or "/" in filename or "\x00" in filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Bad filename")
    path = _SCENES_DIR / filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scene not found")
    return FileResponse(str(path), media_type="image/png")


@router.get("/appearance/{filename}")
async def get_appearance_image(filename: str):
    """Отдать сгенерированный портрет персонажа."""
    if not filename or "\\" in filename or "/" in filename or "\x00" in filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Bad filename")
    path = _APPEARANCE_DIR / filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Appearance not found")
    return FileResponse(str(path), media_type="image/png")


@router.get("/prompt-log")
async def get_prompt_log(character_id: str, limit: int = 5, user_id: str = Depends(get_current_user)):
    """Промпт-аудит: что реально подгружалось в system prompt персонажа.
    Диагностика «почему модель забыла X» — размеры секций, кол-во истории/NPC."""
    if limit > 50:
        limit = 50
    db = await get_db()
    try:
        # Персонаж должен принадлежать текущему юзеру (или это тестовый E2E-юзер)
        owner_cur = await db.execute("SELECT user_id FROM characters WHERE id = ?", (character_id,))
        owner_row = await owner_cur.fetchone()
        if not owner_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
        if owner_row["user_id"] != user_id and not str(user_id).startswith("e2e"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")
        cur = await db.execute(
            """SELECT created_at, system_len, history_msgs, history_chars,
                      sections, npc_registry_count, npc_known_count, full_system
               FROM prompt_log WHERE character_id = ?
               ORDER BY id DESC LIMIT ?""",
            (character_id, limit),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()
    return [
        {
            "created_at": r["created_at"],
            "system_len": r["system_len"],
            "history_msgs": r["history_msgs"],
            "history_chars": r["history_chars"],
            "sections": r["sections"],
            "npc_registry_count": r["npc_registry_count"],
            "npc_known_count": r["npc_known_count"],
            "full_system_preview": (r["full_system"] or "")[:3000],
        }
        for r in rows
    ]


@router.post("", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """Основной endpoint общения с AI-мастером."""
    try:
        await rate_limiter.check(user_id)
        request.user_id = user_id  # перезаписываем из токена, не доверяем клиенту
        return await chat_service.handle_message(request)
    except RateLimitError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except AIError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error in /chat")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Внутренняя ошибка сервера")


@router.post("/stream")
async def chat_stream_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """SSE-стриминг ответа AI-мастера: чанки текста по мере генерации,
    финальное событие done — полный ChatResponse (теги уже обработаны)."""
    try:
        await rate_limiter.check(user_id)
        request.user_id = user_id

        async def event_gen():
            try:
                async for evt in chat_service.stream_message(request):
                    data = _json.dumps(evt, ensure_ascii=False)
                    yield f"data: {data}\n\n"
            except RateLimitError as e:
                yield f"event: error\ndata: {_json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"
            except AIError as e:
                yield f"event: error\ndata: {_json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"
            except Exception:
                logger.exception("Unhandled error in /chat/stream")
                yield f"event: error\ndata: {_json.dumps({'detail': 'Внутренняя ошибка сервера'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # отключаем буферизацию nginx
                "Connection": "keep-alive",
            },
        )
    except RateLimitError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception:
        logger.exception("Unhandled error in /chat/stream setup")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Внутренняя ошибка сервера")


@router.delete("/history/{user_id}")
async def clear_history(user_id: str, current_user: str = Depends(get_current_user)):
    """Очистить историю диалога на сервере."""
    if user_id != current_user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Чужая история недоступна")
    try:
        await rate_limiter.check(user_id)
        await chat_service.clear_history(user_id)
        return {"message": "История очищена"}
    except RateLimitError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception:
        logger.exception("Unhandled error in clear_history")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Внутренняя ошибка сервера")
