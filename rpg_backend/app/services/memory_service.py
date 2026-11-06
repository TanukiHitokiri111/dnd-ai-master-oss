"""
Memory Palace — двухуровневая память для AI-мастера.

Уровень 1 (ближняя память): последние 10 сообщений — полный текст.
Уровень 2 (дальняя память): суммаризированные блоки по 10 сообщений.

Каждые 10 сообщений AI-мастер сжимает их в 3-5 предложений
и сохраняет в БД. При построении контекста: system prompt +
все саммари-блоки + последние 10 сообщений.
"""

import json
import logging
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import POLZA_EXTRA_BODY, settings
from app.db import get_db

logger = logging.getLogger(__name__)

# Константы
SUMMARIZE_EVERY_N = 10  # сжимать каждые 10 сообщений
RECENT_MESSAGES_COUNT = 10  # хранить последние 10 сообщений детально

# Промпт для суммаризации — просим модель выделить ключевую информацию
_SUMMARIZE_PROMPT = """Ты — архивариус D&D. Суммаризируй этот фрагмент игровой сессии в 3-5 предложений на русском.

Выдели ТОЛЬКО существенное:
- Ключевые события (что произошло)
- Важные NPC (с кем встретились, имя + роль)
- Предметы (что нашли/получили/потеряли)
- Локации (где были, куда направляются)
- Квесты/решения (какие обязательства взяли, что решили)

Формат ответа — строго JSON на одной строке:
{"summary":"...","key_npcs":["имя — роль"],"key_items":["предмет"],"key_locations":["локация"],"key_quests":["квест"]}

Не придумывай того чего не было. Если чего-то нет — пустой массив."""


async def _build_character_card(db, character_id: str) -> str:
    """Построить компактную карточку персонажа для вставки в саммари."""
    cursor = await db.execute(
        "SELECT name, race, class_name, subclass, subrace, level, xp, "
        "hp_max, hp_current, ac, init_ac, speed, "
        "stats, features, proficiencies, skill_proficiencies, languages "
        "FROM characters WHERE id = ?",
        (character_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return ""

    r = dict(row)
    stats = json.loads(r["stats"]) if isinstance(r["stats"], str) and r["stats"] else {}
    skills = json.loads(r["skill_proficiencies"]) if isinstance(r["skill_proficiencies"], str) and r["skill_proficiencies"] else []
    features = json.loads(r["features"]) if isinstance(r["features"], str) and r["features"] else []
    langs = json.loads(r["languages"]) if isinstance(r["languages"], str) and r["languages"] else []

    def mod(v): return (v - 10) // 2
    def mod_str(v): return f"+{mod(v)}" if mod(v) >= 0 else str(mod(v))

    # Раса + подраса
    race_str = r["race"]
    if r.get("subrace"):
        race_str += f" ({r['subrace']})"

    # Класс + подкласс
    class_str = r["class_name"]
    if r.get("subclass"):
        class_str += f" ({r['subclass']})"

    lines = [
        f"## 🎭 {r['name']} — {race_str} {class_str}, ур. {r['level']} (XP: {r['xp']})",
        f"❤️ HP: {r['hp_current']}/{r['hp_max']} | 🛡️ AC: {r['ac']} | ⚡ Скорость: {r['speed']} фт",
        f"📊 СТР {stats.get('str',10)} ({mod_str(stats.get('str',10))}) | "
        f"ЛОВ {stats.get('dex',10)} ({mod_str(stats.get('dex',10))}) | "
        f"ТЕЛ {stats.get('con',10)} ({mod_str(stats.get('con',10))}) | "
        f"ИНТ {stats.get('int',10)} ({mod_str(stats.get('int',10))}) | "
        f"МДР {stats.get('wis',10)} ({mod_str(stats.get('wis',10))}) | "
        f"ХАР {stats.get('cha',10)} ({mod_str(stats.get('cha',10))})",
    ]

    if skills:
        lines.append(f"🎯 Навыки: {', '.join(skills[:8])}")
    if langs:
        lines.append(f"🗣️ Языки: {', '.join(langs)}")
    if features:
        feat_names = [f.get('name', f) if isinstance(f, dict) else str(f) for f in features[:8]]
        lines.append(f"✨ Умения: {', '.join(feat_names)}")

    return "\n".join(lines)


async def _get_client() -> AsyncOpenAI:
    """Ленивый клиент для суммаризации."""
    return AsyncOpenAI(
        base_url=settings.llm_api_base_url,
        api_key=settings.llm_api_key,
        timeout=60.0,
    )


async def _last_summarized_message_id(
    db, table: str, key_column: str, key_value: str
) -> int | None:
    """ID последнего сообщения, которое уже попало в саммари."""
    cursor = await db.execute(
        f"SELECT MAX(last_message_id) FROM {table} WHERE {key_column} = ?",
        (key_value,),
    )
    row = await cursor.fetchone()
    return row[0] if row and row[0] is not None else None


async def should_summarize_session(session_id: str) -> bool:
    """Проверить: накопилось ли 10+ необработанных сообщений в сессии."""
    db = await get_db()
    try:
        last_done = await _last_summarized_message_id(
            db, "session_memory", "session_id", session_id
        )

        if last_done is None:
            # Ни разу не суммаризировали — берём все сообщения
            cursor = await db.execute(
                "SELECT COUNT(*) FROM game_messages WHERE session_id = ?",
                (session_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM game_messages WHERE session_id = ? AND id > ?",
                (session_id, last_done),
            )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        return count >= SUMMARIZE_EVERY_N
    finally:
        await db.close()


async def should_summarize_user(user_id: str, character_id: str | None = None) -> bool:
    """Проверить: накопилось ли 10+ необработанных сообщений у пользователя."""
    db = await get_db()
    try:
        last_done = await _last_summarized_message_id(
            db, "user_memory", "user_id", user_id
        )

        if last_done is None:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM chat_history WHERE user_id = ? AND character_id IS ?",
                (user_id, character_id or ""),
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM chat_history WHERE user_id = ? AND character_id IS ? AND id > ?",
                (user_id, character_id or "", last_done),
            )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        return count >= SUMMARIZE_EVERY_N
    finally:
        await db.close()


async def _fetch_unsummarized_messages(
    db, table: str, key_column: str, key_value: str,
    last_done_id: int | None, limit: int = SUMMARIZE_EVERY_N,
    character_id: str | None = None,
) -> list[dict]:
    """Загрузить N необработанных сообщений для суммаризации."""
    char_clause = " AND character_id IS ?" if character_id is not None else ""
    char_val = (character_id or "",) if character_id is not None else ()
    if last_done_id is None:
        cursor = await db.execute(
            f"SELECT id, role, content FROM {table} "
            f"WHERE {key_column} = ?{char_clause} AND role != 'system' "
            f"ORDER BY id ASC LIMIT ?",
            (key_value,) + char_val + (limit,),
        )
    else:
        cursor = await db.execute(
            f"SELECT id, role, content FROM {table} "
            f"WHERE {key_column} = ?{char_clause} AND id > ? AND role != 'system' "
            f"ORDER BY id ASC LIMIT ?",
            (key_value,) + char_val + (last_done_id, limit),
        )
    rows = await cursor.fetchall()
    return [{"id": r["id"], "role": r["role"], "content": r["content"]} for r in rows]


async def summarize_session_messages(session_id: str) -> dict | None:
    """Суммаризировать последние 10 необработанных сообщений сессии."""
    db = await get_db()
    try:
        last_done = await _last_summarized_message_id(
            db, "session_memory", "session_id", session_id
        )

        messages = await _fetch_unsummarized_messages(
            db, "game_messages", "session_id", session_id, last_done
        )

        if len(messages) < SUMMARIZE_EVERY_N:
            return None  # ещё рано

        # Формируем текст для суммаризации
        text = "\n".join(
            f"[{'Мастер' if m['role'] == 'assistant' else 'Игрок'}]: {m['content']}"
            for m in messages
        )

        # Получаем номер следующего блока
        cursor = await db.execute(
            "SELECT MAX(block_number) FROM session_memory WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        next_block = (row[0] or 0) + 1

        first_msg_id = messages[0]["id"]
        last_msg_id = messages[-1]["id"]

    finally:
        await db.close()

    # Вызываем AI для суммаризации (вне транзакции)
    raw = ""
    client = await _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=800,
            extra_body=POLZA_EXTRA_BODY,
        )
        raw = response.choices[0].message.content or "{}"
        # Чистим markdown-обёртки если модель их добавила
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Summarize parse failed: %s | raw=%s", e, raw[:200])
        # Fallback: сохраняем сырой текст как summary
        parsed = {
            "summary": text[:500],
            "key_npcs": [],
            "key_items": [],
            "key_locations": [],
            "key_quests": [],
        }

    # Сохраняем в БД
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO session_memory
               (session_id, block_number, summary, message_count,
                first_message_id, last_message_id,
                key_npcs, key_items, key_locations, key_quests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id, next_block,
                parsed.get("summary", ""),
                len(messages),
                first_msg_id, last_msg_id,
                json.dumps(parsed.get("key_npcs", []), ensure_ascii=False),
                json.dumps(parsed.get("key_items", []), ensure_ascii=False),
                json.dumps(parsed.get("key_locations", []), ensure_ascii=False),
                json.dumps(parsed.get("key_quests", []), ensure_ascii=False),
            ),
        )
        await db.commit()
        logger.info(
            "session_memory: session=%s block=%d msgs=%d",
            session_id[:8], next_block, len(messages),
        )
    finally:
        await db.close()

    return parsed


async def summarize_user_messages(user_id: str, character_id: str | None = None) -> dict | None:
    """Суммаризировать последние 10 необработанных сообщений соло-игры."""
    db = await get_db()
    try:
        last_done = await _last_summarized_message_id(
            db, "user_memory", "user_id", user_id
        )

        messages = await _fetch_unsummarized_messages(
            db, "chat_history", "user_id", user_id, last_done, character_id=character_id
        )

        if len(messages) < SUMMARIZE_EVERY_N:
            return None

        text = "\n".join(
            f"[{'Мастер' if m['role'] == 'assistant' else 'Игрок'}]: {m['content']}"
            for m in messages
        )

        cursor = await db.execute(
            "SELECT MAX(block_number) FROM user_memory WHERE user_id = ? AND character_id IS ?",
            (user_id, character_id or ""),
        )
        row = await cursor.fetchone()
        next_block = (row[0] or 0) + 1

        first_msg_id = messages[0]["id"]
        last_msg_id = messages[-1]["id"]
    finally:
        await db.close()

    # Строим карточку персонажа (раса, класс, статы, навыки)
    card_text = ""
    if character_id:
        db2 = await get_db()
        try:
            card_text = await _build_character_card(db2, character_id)
        finally:
            await db2.close()

    raw = ""
    client = await _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=800,
            extra_body=POLZA_EXTRA_BODY,
        )
        raw = response.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Summarize user parse failed: %s | raw=%s", e, raw[:200])
        parsed = {
            "summary": text[:500],
            "key_npcs": [],
            "key_items": [],
            "key_locations": [],
            "key_quests": [],
        }

    db = await get_db()
    try:
        full_summary = parsed.get("summary", "")
        if card_text:
            full_summary = card_text + "\n\n" + full_summary

        await db.execute(
            """INSERT INTO user_memory
               (user_id, character_id, block_number, summary, message_count,
                first_message_id, last_message_id,
                key_npcs, key_items, key_locations, key_quests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, character_id or "", next_block,
                full_summary,
                len(messages),
                first_msg_id, last_msg_id,
                json.dumps(parsed.get("key_npcs", []), ensure_ascii=False),
                json.dumps(parsed.get("key_items", []), ensure_ascii=False),
                json.dumps(parsed.get("key_locations", []), ensure_ascii=False),
                json.dumps(parsed.get("key_quests", []), ensure_ascii=False),
            ),
        )
        await db.commit()
        logger.info(
            "user_memory: user=%s block=%d msgs=%d",
            user_id[:8], next_block, len(messages),
        )
    finally:
        await db.close()

    return parsed


async def load_session_memories(session_id: str) -> str:
    """Загрузить все саммари-блоки сессии как одну строку для system prompt."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT summary, key_npcs, key_items, key_locations, key_quests "
            "FROM session_memory WHERE session_id = ? ORDER BY block_number ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return ""

        parts = ["## 📜 ИСТОРИЯ СЕССИИ\n"]
        for i, r in enumerate(rows, 1):
            parts.append(f"**Часть {i}:** {r['summary']}")

            # Добавляем структурированные данные если есть
            for field, label in [
                ("key_npcs", "👤 NPC"),
                ("key_items", "🎒 Предметы"),
                ("key_locations", "📍 Локации"),
                ("key_quests", "⚔️ Квесты"),
            ]:
                try:
                    items = json.loads(r[field]) if isinstance(r[field], str) else r[field]
                    if items:
                        parts.append(f"  {label}: {', '.join(items)}")
                except (json.JSONDecodeError, TypeError):
                    pass
            parts.append("")

        return "\n".join(parts)
    finally:
        await db.close()


async def load_user_memories(user_id: str, character_id: str | None = None) -> str:
    """Загрузить все саммари-блоки соло-игрока для system prompt."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT summary, key_npcs, key_items, key_locations, key_quests "
            "FROM user_memory WHERE user_id = ? AND character_id IS ? ORDER BY block_number ASC",
            (user_id, character_id or ""),
        )
        rows = await cursor.fetchall()
        if not rows:
            return ""

        parts = ["## 📜 ИСТОРИЯ ПРИКЛЮЧЕНИЙ\n"]
        for i, r in enumerate(rows, 1):
            parts.append(f"**Глава {i}:** {r['summary']}")
            for field, label in [
                ("key_npcs", "👤 NPC"),
                ("key_items", "🎒 Предметы"),
                ("key_locations", "📍 Локации"),
                ("key_quests", "⚔️ Квесты"),
            ]:
                try:
                    items = json.loads(r[field]) if isinstance(r[field], str) else r[field]
                    if items:
                        parts.append(f"  {label}: {', '.join(items)}")
                except (json.JSONDecodeError, TypeError):
                    pass
            parts.append("")

        return "\n".join(parts)
    finally:
        await db.close()
