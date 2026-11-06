"""Миксин обработки тегов: путешествия, паузы, погода."""
import json
import re

from app.db import get_db
from app.logger import logger

class TravelMixin:
    """Путешествия: TRAVEL, BREAK, погода/время."""

    async def _process_break_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Вытащить [BREAK: key] теги и удалить сломанные предметы у персонажа."""
        import re
        from app.knowledge.item_utils import resolve_item

        broken = []
        clean = reply

        for m in re.finditer(r'\[BREAK:\s*([^\]]+)\]', reply):
            item_key = m.group(1).strip()
            item_info = resolve_item(item_key)
            resolved_key = item_info["item_key"] if item_info else item_key

            if character_id:
                db = await get_db()
                try:
                    # Удаляем ОДИН экземпляр предмета с этим ключом
                    cur = await db.execute(
                        """SELECT id FROM items WHERE character_id = ? AND item_key = ? LIMIT 1""",
                        (character_id, resolved_key),
                    )
                    row = await cur.fetchone()
                    if not row:
                        # Фолбэк: ищем по русскому названию (item_name).
                        # Нужно для [BREAK: рапира] когда в БД лежит item_key='rapier',
                        # а resolve_item не покрыл название (кастомный предмет).
                        name_match = item_key.lower().strip()
                        cur2 = await db.execute(
                            """SELECT id FROM items WHERE character_id = ? AND LOWER(item_name) = ? LIMIT 1""",
                            (character_id, name_match),
                        )
                        row = await cur2.fetchone()
                    if row:
                        await db.execute("DELETE FROM items WHERE id = ?", (row[0],))
                    await db.commit()
                finally:
                    await db.close()

            broken.append(resolved_key)
            name = item_info["item_name"] if item_info else item_key.replace("_", " ").title()
            clean = clean.replace(m.group(0), f"~~{name}~~" if item_info else f"~~{item_key}~~", 1)

        return clean, broken


    # ── _process_combat_end_tags ──


    async def _process_travel_tags(self, reply: str, character_id: str | None, user_id: str | None = None) -> tuple[str, dict | None]:
        """Обработать [TRAVEL: город] — персонаж прибыл в новый город.

        Валидирует город по WORLD_MAP, обновляет game_state.location,
        добавляет город в discovered_locations. Возвращает (clean_reply, city_info).
        """
        from app.knowledge.worlds import WORLD_MAP, WORLD_MAP_ALIASES, normalize_city

        m = re.search(r'\[TRAVEL:\s*([^\]]+)\]', reply)
        if not m:
            return reply, None
        city_raw = m.group(1).strip()
        city_key = normalize_city(city_raw)
        clean = re.sub(r'\[TRAVEL:\s*[^\]]+\]', '', reply).strip()

        if not city_key:
            logger.info("🗺️ TRAVEL char=%s неизвестный город «%s» — тег проигнорирован", character_id[:12] if character_id else "?", city_raw)
            return clean, None

        city = WORLD_MAP.get(city_key, {})
        city_info_out = {"key": city_key, "name": city.get("name", city_key)}

        if character_id:
            db = await get_db()
            try:
                # Обновляем локацию; сцена и бой из прошлой локации не переносятся
                await db.execute(
                    "UPDATE game_state SET location = ?, scene = '', combat = '{}', updated_at = datetime('now') WHERE user_id = ? AND character_id IS ?",
                    (city.get("name", city_key), user_id or "", character_id),
                )
                # Добавляем в discovered_locations
                cur = await db.execute(
                    "SELECT discovered_locations FROM game_state WHERE user_id = ? AND character_id IS ? ORDER BY updated_at DESC LIMIT 1",
                    (user_id or "", character_id),
                )
                row = await cur.fetchone()
                discovered = []
                if row and row["discovered_locations"]:
                    try:
                        discovered = json.loads(row["discovered_locations"])
                    except Exception:
                        discovered = []
                if city_key not in discovered:
                    discovered.append(city_key)
                await db.execute(
                    "UPDATE game_state SET discovered_locations = ?, updated_at = datetime('now') WHERE user_id = ? AND character_id IS ?",
                    (json.dumps(discovered, ensure_ascii=False), user_id or "", character_id),
                )
                await db.commit()
                logger.info("🗺️ TRAVEL char=%s → %s (открыто городов: %d)", character_id[:12], city.get("name", city_key), len(discovered))
            except Exception:
                logger.exception("Travel tag processing failed")
            finally:
                await db.close()

        return clean, city_info_out


    # ── _process_xp_tags ──


    @staticmethod
    def _weather_and_time(location: str) -> str:
        """Детерминированная погода + время суток для живой атмосферы мира.

        Время суток — реальное (UTC), погода — по локации с дневным сидом,
        чтобы мир не скакал хаотично, но менялся день ото дня.
        """
        import hashlib
        from datetime import datetime, timezone

        hour = datetime.now(timezone.utc).hour
        if 5 <= hour < 11:
            tod = "🌅 утро"
            tod_note = "мир просыпается, улицы пустеют к полудню"
        elif 11 <= hour < 17:
            tod = "☀️ день"
            tod_note = "самое оживлённое время"
        elif 17 <= hour < 22:
            tod = "🌇 вечер"
            tod_note = "сумерки, зажигаются огни, таверны полны"
        else:
            tod = "🌙 ночь"
            tod_note = "темно, фонари и луна, ночные твари активнее"

        loc_l = (location or "").lower()
        # Климатическая база по типу локации
        if any(w in loc_l for w in ["подземель", "пещер", "катакомб", "склеп", "шахт", "рудник"]):
            weather = "под землёй: прохладно, сыро, капает вода"
        elif any(w in loc_l for w in ["пустын", "дюн", "сахар"]):
            weather = "зной, сухой воздух дрожит над песком"
        elif any(w in loc_l for w in ["гор", "перевал", "вершин", "ледник", "север"]):
            weather = "холодный ветер, снежные шапки, морозный воздух"
        elif any(w in loc_l for w in ["лес", "рощ", "чащ", "чаща"]):
            weather = "плотный лесной воздух, солнечные пятна сквозь кроны, пахнет прелой листвой"
        elif any(w in loc_l for w in ["болот", "топь", "мхи"]):
            weather = "туман стелется над водой, комары, чавкающая грязь"
        elif any(w in loc_l for w in ["мор", "порт", "берег", "побереж", "гаван", "док"]):
            weather = "солёный бриз с воды, крики чаек"
        elif any(w in loc_l for w in ["город", "таверн", "трактир", "деревн", "посёлок", "базар", "храм", "замок", "крепост"]):
            weather = "умеренно, в зависимости от сезона; город живёт своей жизнью"
        else:
            # Универсальная погода по дневному сиду
            day_seed = int(hashlib.md5((location or "world").encode()).hexdigest()[:8], 16)
            day_idx = (day_seed + datetime.now(timezone.utc).timetuple().tm_yday) % 6
            weather = [
                "ясно, лёгкие облака",
                "пасмурно, серое небо",
                "моросит мелкий дождь",
                "пронизывающий ветер, редкие порывы",
                "густой туман, видимость плохая",
                "гроза вдалеке, воздух пахнет озоном",
            ][day_idx]

        return (f"=== 🌦️ МИР СЕЙЧАС ===\n"
                f"Время суток: {tod} ({tod_note})\n"
                f"Погода: {weather}\n"
                f"Описывай это в сценах (не пересказывай сухо — вплетай в атмосферу), "
                f"если только игрок не находится в помещении без окон.")


