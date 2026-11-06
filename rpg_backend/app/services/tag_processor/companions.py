from app.db import get_db
from app.logger import logger

class CompanionsMixin:
    """Компаньоны: список для промпта, теги COMPANION."""

    async def _upsert_companion(
        self, character_id: str, name: str,
        updates: dict, defaults: dict | None = None,
    ) -> int | None:
        """Общий upsert спутника: SELECT id → UPDATE (updates) или INSERT (defaults+updates).

        Возвращает id существующей строки (если обновляли) или None (создали /
        нет строки и defaults не задан). Единственная точка доступа к таблице
        companions для _process_companion_tags и _process_companion_state_tags.
        """
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT id FROM companions WHERE character_id = ? AND name = ?",
                (character_id, name),
            )
            row = await cur.fetchone()
            if row:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                await db.execute(
                    f"UPDATE companions SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                    [*updates.values(), row["id"]],
                )
                await db.commit()
                return row["id"]
            if defaults is None:
                return None
            cols = {"character_id": character_id, "name": name, **defaults, **updates}
            placeholders = ", ".join("?" for _ in cols)
            await db.execute(
                f"INSERT INTO companions ({', '.join(cols)}) VALUES ({placeholders})",
                list(cols.values()),
            )
            await db.commit()
            return None
        finally:
            await db.close()

    async def _get_companions_for_prompt(self, character_id: str) -> str:
        """Список спутников персонажа для system prompt."""
        try:
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT name, species, description, mood, status FROM companions WHERE character_id = ? AND status != 'умер' ORDER BY id",
                    (character_id,),
                )
                rows = await cur.fetchall()
                if not rows:
                    return ""
                lines = []
                for r in rows:
                    mood_str = f" (настроение: {r['mood']})" if r["mood"] and r["mood"] != "нейтральное" else ""
                    lines.append(f"- {r['name']} ({r['species']}{mood_str}): {r['description']}")
                return "=== 🐾 СПУТНИКИ ИГРОКА ===\n" + "\n".join(lines)
            finally:
                await db.close()
        except Exception:
            logger.exception("get companions failed")
            return ""


    # ── _walk_companion_tags ──


    async def _walk_companion_tags(
        self, reply: str, character_id: str | None, tag_name: str,
    ) -> tuple[str, list[str], list[str]]:
        """Общий walker тегов [COMPANION: имя|вид|описание] / [COMPANION_STATE: имя|настроение|статус].

        Возвращает (clean_reply, names, fields):
        - names — обработанные имена спутников;
        - fields — значения второго поля (вид для COMPANION, настроение для COMPANION_STATE).
        Для COMPANION_STATE передаёт третье поле (статус) в _upsert_companion через status_extra.
        """
        import re

        names: list[str] = []
        fields: list[str] = []
        clean = reply

        pattern = (
            r'\[' + tag_name + r':\s*([^|\]]+)\s*\|\s*([^|\]]+)\s*\|\s*([^\]]+)\]'
        )
        for m in re.finditer(pattern, reply):
            name = m.group(1).strip()
            field2 = m.group(2).strip()
            field3 = m.group(3).strip()
            if not name:
                continue

            if character_id:
                if tag_name == "COMPANION":
                    await self._upsert_companion(
                        character_id, name,
                        updates={"species": field2, "description": field3},
                        defaults={"mood": "нейтральное", "status": "active"},
                    )
                    names.append(name)
                    fields.append(field2)
                    logger.info("🐾 COMPANION char=%s %s (%s)", character_id[:12], name, field2)
                    clean = clean.replace(m.group(0), f"🐾 *{name}*", 1)
                else:  # COMPANION_STATE
                    updated_id = await self._upsert_companion(
                        character_id, name,
                        updates={"mood": field2, "status": field3},
                    )
                    if updated_id:
                        names.append(name)
                        fields.append(field2)
                        logger.info("🐾 COMPANION_STATE char=%s %s → %s/%s",
                                    character_id[:12], name, field2, field3)
                    clean = clean.replace(m.group(0), "", 1)

        return clean, names, fields

    async def _process_companion_state_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Вытащить [COMPANION_STATE: имя|настроение|статус] — обновить состояние спутника.

        Настроение: радостное/злое/напуганное/грустное/нейтральное...
        Статус: active/умер/убежал/ранен...
        """
        clean, _names, _moods = await self._walk_companion_tags(reply, character_id, "COMPANION_STATE")
        return clean, _names

    async def _process_companion_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Вытащить [COMPANION: имя|вид|описание] — добавить/обновить спутника.

        Спутник — существо или соратник, путешествующий с персонажем.
        Если спутник с таким именем уже есть — обновляем описание, иначе создаём.
        """
        clean, names, _species = await self._walk_companion_tags(reply, character_id, "COMPANION")
        return clean, names


    # ── _process_gold_tags ──

