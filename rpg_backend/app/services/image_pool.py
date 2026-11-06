"""Пул переиспользуемых картинок (image_assets) + выдача с учётом просмотров.

Раньше один и тот же четырёхшаговый протокол SELECT unseen → SELECT fallback →
UPDATE use_count → INSERT image_views копировался трижды (сцены —
SceneGeneratorMixin._pick_pool_scene, NPC — NpcMixin._pick_pool_npc, NPC-пул
— NpcMixin._npc_pool_size + _scene_pool_size). Теперь весь доступ к
image_assets/image_views живёт здесь, а миксины вызывают готовые функции.

`kind` distinguishes scene ('scene', ключ location_key) от NPC ('npc', ключ
npc_name) записей; остальные столбцы идентичны.
"""

import json
import logging
import uuid

from app.db import get_db

logger = logging.getLogger(__name__)

__all__ = [
    "IMAGE_POOL_KINDS",
    "image_pool_size",
    "pick_unviewed_from_pool",
    "mark_viewed_on",
    "save_npc_entry",
]

IMAGE_POOL_KINDS = frozenset({"scene", "npc", "character"})


def _validate(kind: str, key_column: str, key_value: str) -> None:
    if kind not in IMAGE_POOL_KINDS:
        raise ValueError(f"Invalid image_assets kind: {kind}")
    if key_column not in ("location_key", "npc_name"):
        raise ValueError(f"Invalid pool key column: {key_column}")
    if not key_value:
        raise ValueError("Pool key value must be non-empty")


async def image_pool_size(kind: str, key_column: str, key_value: str) -> int:
    """Сколько картинок этого ключа уже в пуле (kind + location_key/npc_name)."""
    _validate(kind, key_column, key_value)
    db = await get_db()
    try:
        cur = await db.execute(
            f"SELECT COUNT(*) AS n FROM image_assets WHERE kind = ? AND {key_column} = ?",
            (kind, key_value),
        )
        row = await cur.fetchone()
        return row["n"] if row else 0
    except Exception:
        logging.getLogger(__name__).exception("image_pool_size failed")
        return 0
    finally:
        await db.close()


async def pick_unviewed_from_pool(kind: str, key_column: str, key_value: str, user_id: str) -> str | None:
    """Взять из пула картинку, которую этот игрок ещё не видел.

    Сначала ищем по image_views (не видел → наименее использованную), если все
    видел — берём наименее использованную в принципе (ротация). Успешная выдача
    инкрементирует use_count и регистрирует просмотр (атомарно, одно соединение).
    """
    _validate(kind, key_column, key_value)
    db = await get_db()
    try:
        order = "ORDER BY a.use_count ASC, a.last_used_at IS NULL DESC, a.created_at ASC"
        cur = await db.execute(
            f"""SELECT a.url FROM image_assets a
                WHERE a.kind = ? AND a.{key_column} = ?
                  AND a.id NOT IN (SELECT asset_id FROM image_views WHERE user_id = ?)
                {order} LIMIT 1""",
            (kind, key_value, user_id),
        )
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE image_assets SET use_count = use_count + 1, last_used_at = datetime('now') WHERE url = ?",
                (row["url"],),
            )
            await mark_viewed_on(db, row["url"], user_id)
            await db.commit()
            return row["url"]

        # Все видел — ротация: наименее использованная в принципе.
        cur = await db.execute(
            f"""SELECT a.url, a.id FROM image_assets a
                WHERE a.kind = ? AND a.{key_column} = ?
                {order} LIMIT 1""",
            (kind, key_value),
        )
        row = await cur.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE image_assets SET use_count = use_count + 1, last_used_at = datetime('now') WHERE id = ?",
            (row["id"],),
        )
        await mark_viewed_on(db, row["url"], user_id)
        await db.commit()
        return row["url"]
    except Exception:
        logger.exception("Pool pick failed (kind=%s)", kind)
        return None
    finally:
        await db.close()


async def mark_viewed_on(db, url: str, user_id: str) -> None:
    """Отметить просмотр на ОТКРЫТОМ соединении (без commit — решает вызывающий)."""
    if not user_id or not url:
        return
    cur = await db.execute("SELECT id FROM image_assets WHERE url = ?", (url,))
    row = await cur.fetchone()
    if row:
        await db.execute(
            "INSERT OR IGNORE INTO image_views (asset_id, user_id, viewed_at) VALUES (?, ?, datetime('now'))",
            (row["id"], user_id),
        )


async def save_npc_entry(url: str, npc_name: str = "", character_id: str = "",
                         meta: dict | None = None, tags: list | None = None) -> None:
    """Добавить картинку NPC/портрет в общий пул image_assets (kind='npc'|'character')."""
    try:
        kind = "npc" if npc_name else "character"
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO image_assets
                   (id, kind, location_key, npc_name, character_id, meta, tags, url, file_name, use_count, last_used_at, created_at)
                   VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, 0, NULL, datetime('now'))""",
                (
                    str(uuid.uuid4()),
                    kind,
                    npc_name,
                    character_id or "",
                    json.dumps(meta or {}, ensure_ascii=False),
                    json.dumps(tags or [], ensure_ascii=False),
                    url,
                    url.rsplit("/", 1)[-1],
                ),
            )
            await db.commit()
        finally:
            await db.close()
    except Exception as e:
        logger.warning("NPC asset save failed: %s", e)
