"""Миксин обработки тегов: предметы, магазин, заклинания, золото."""
import base64
import os
import re

from app.db import get_db
from app.logger import logger
# Импорт модульных функций из base.py (транзакции золота + магазин)
from app.services.tag_processor.base import process_gold_tags, process_shop_tags_ex

# Лимит инвентаря для покупок с явной ценой ([SHOP: ключ|цена]) в личном чате
SHOP_INVENTORY_LIMIT = 100


class ItemsMixin:
    """Инвентарь: предметы, магазин/продажа, заклинания, золото."""

    async def _process_gold_tags(self, reply: str, character_id: str | None) -> tuple[str, int | None]:
        """Тонкий враппер над модульной process_gold_tags."""
        return await process_gold_tags(reply, character_id)


    # ── _process_hp_tags ──


    async def _process_item_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Вытащить [ITEM: key] теги из ответа DM и выдать предметы персонажу.

        Дедуп: если предмет с таким ключом уже есть у персонажа — НЕ создаём
        дубль, а увеличиваем qty (для расходников) или пропускаем (для оружия/
        брони, где второй экземпляр бессмыслен). Это чинит «появлялось
        дополнительное оружие» — раньше каждый [ITEM: rapier] делал INSERT.
        """
        from app.knowledge.item_utils import resolve_item

        saved = []
        clean = reply

        for m in re.finditer(r'\[ITEM:\s*([^\]]+)\]', reply):
            item_key = m.group(1).strip()
            item_info = resolve_item(item_key)

            if character_id and item_info:
                db = await get_db()
                try:
                    slot = item_info.get("slot", "inventory")
                    flavor = item_info.get("flavor", item_info.get("description", ""))
                    # Дедуп: ищем уже существующий предмет с таким ключом
                    cur = await db.execute(
                        "SELECT id, qty FROM items WHERE character_id = ? AND item_key = ?",
                        (character_id, item_info["item_key"]),
                    )
                    existing = await cur.fetchone()
                    if existing:
                        # Оружие/броня: не дублируем, qty не увеличиваем (второй
                        # экземпляр бессмыслен). Расходники (стрелы, пайки) — qty+1.
                        itype = item_info.get("item_type", "gear")
                        if itype in ("weapon", "armor"):
                            pass  # уже есть — пропускаем
                        else:
                            new_qty = (existing[1] or 1) + 1
                            await db.execute(
                                "UPDATE items SET qty = ? WHERE id = ?", (new_qty, existing[0]),
                            )
                        await db.commit()
                    else:
                        await db.execute(
                            """INSERT INTO items (character_id, item_key, item_name, item_type, item_subtype, qty, slot, equipped, attunement, notes, modifiers, flavor)
                               VALUES (?, ?, ?, ?, ?, 1, ?, 0, 0, '', '{}', ?)""",
                            (character_id, item_info["item_key"], item_info["item_name"], item_info.get("item_type", "gear"),
                             item_info.get("item_subtype", ""), slot, flavor),
                        )
                        await db.commit()
                finally:
                    await db.close()
                saved.append(item_info["item_key"])

            clean = clean.replace(m.group(0), f"*{item_info['item_name']}*" if item_info else f"*{item_key.replace('_', ' ').title()}*", 1)

        return clean, saved


    # ── _process_karma_tags ──


    async def _process_shop_tags(self, reply: str, character_id: str | None) -> tuple[str, int | None]:
        """Обработать [SHOP: ключ|цена] или [SHOP: ключ] — покупка, [SELL: ...] — продажа.

        Покупка: списывает золото (проверка баланса!), выдаёт предмет в инвентарь.
        Личный чат дополнительно проверяет переполнение инвентаря при покупке
        с явной ценой (макс SHOP_INVENTORY_LIMIT предметов).
        [SHOP: ключ] без цены — цена auto из value_gp каталога × (1.5..3.0).
        Продажа: удаляет предмет, начисляет золото (50% от рыночной цены).
        [SELL: ключ] без цены — цена auto из value_gp × 0.4.
        Возвращает (clean_reply, gold_after) — золото после операции (None если тегов нет).

        Тонкий враппер над общим движком process_shop_tags_ex (без клонов с
        модульной process_shop_tags для группового чата).
        """
        return await process_shop_tags_ex(reply, character_id, priced_inventory_limit=SHOP_INVENTORY_LIMIT)


    # ── _process_spell_tags ──


    async def _save_custom_spell(self, character_id: str, spell_data: dict) -> str:
        """Сохранить заклинание, созданное в диалоге (JSON-формат тега).

        Возвращает имя сохранённого заклинания.
        """
        name = spell_data.get("name", "Неизвестное заклинание")
        custom_key = f"custom_{base64.urlsafe_b64encode(os.urandom(6)).decode()[:8]}"
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO character_spells
                   (character_id, spell_key, spell_name, spell_level, school, "desc", casting_time, "range", components, duration, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Создано в диалоге с DM')""",
                (character_id, custom_key, name,
                 spell_data.get("level", 1), spell_data.get("school", ""),
                 spell_data.get("desc", ""), spell_data.get("casting_time", ""),
                 spell_data.get("spell_range", spell_data.get("range", "")),
                 spell_data.get("components", ""), spell_data.get("duration", "")),
            )
            await db.commit()
        finally:
            await db.close()
        return name


    def _extract_spell_json_tags(self, reply: str) -> tuple[list[str], list[str]]:
        """Найти [SPELL: {json}] теги балансированным парсером скобок.

        Возвращает (полные_теги, json_строки). Незбалансированные и битые
        JSON пропускаются с warning в лог.
        """
        import json as _json

        fulls: list[str] = []
        jsons: list[str] = []
        pos = 0
        while True:
            start = reply.find("[SPELL:", pos)
            if start == -1:
                break
            j = self._skip_ws_after_prefix(reply, start + len("[SPELL:"))
            if j is None:
                pos = start + 1
                continue
            end = self._match_json_braces(reply, j)
            if end is None:
                logger.warning("SPELL tag unbalanced braces at %d", start)
                pos = start + 1
                continue
            json_str = reply[j:end + 1]
            try:
                _json.loads(json_str)
            except _json.JSONDecodeError:
                logger.warning("SPELL tag invalid JSON: %.160s", json_str)
                pos = end + 1
                continue
            fulls.append(reply[start:end + 2])
            jsons.append(json_str)
            pos = end + 1
        return fulls, jsons

    @staticmethod
    def _skip_ws_after_prefix(reply: str, j: int) -> int | None:
        """Пропустить пробелы после '[SPELL:'; None если '{' не найден."""
        while j < len(reply) and reply[j] in " \t\n":
            j += 1
        if j >= len(reply) or reply[j] != "{":
            return None
        return j

    @staticmethod
    def _match_json_braces(reply: str, start: int) -> int | None:
        """Найти конец JSON-объекта, начинающегося с reply[start]=='{'.

        Возвращает индекс закрывающей '}' или None при дисбалансе.
        """
        depth = 0
        i = start
        while i < len(reply):
            if reply[i] == "{":
                depth += 1
            elif reply[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None


    async def _process_custom_spell_tag(self, reply: str, tag: str, json_str: str,
                                        character_id: str | None) -> tuple[str, str]:
        """Обработать один [SPELL: {json}] тег.

        Возвращает (clean_фрагмент_замены, имя_заклинания).
        """
        import json as _json

        spell_data = _json.loads(json_str)
        name = spell_data.get("name", "Неизвестное заклинание")
        if character_id:
            await self._save_custom_spell(character_id, spell_data)
        return f"✅ *{name}* добавлено в книгу заклинаний!", name


    def _lookup_known_spell(self, spell_key: str) -> dict | None:
        """Найти заклинание по ключу в каталоге SPELLS_BY_CLASS."""
        from app.knowledge.srd_rules import SPELLS_BY_CLASS
        for spells in SPELLS_BY_CLASS.values():
            for s in spells:
                if s["key"] == spell_key:
                    return s
        return None


    async def _save_catalog_spell(self, character_id: str, spell_key: str, spell_info: dict | None) -> None:
        """Вставить известное (или заглушку неизвестного) заклинание в книгу персонажа.

        INSERT OR IGNORE — повторная находка того же свитка не дублирует строку.
        """
        db = await get_db()
        try:
            if spell_info:
                await db.execute(
                    """INSERT OR IGNORE INTO character_spells
                       (character_id, spell_key, spell_name, spell_level, school, "desc", casting_time, "range", components, duration, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Найдено в приключении')""",
                    (character_id, spell_key, spell_info["name"], spell_info["level"],
                     spell_info["school"], spell_info["desc"], spell_info["casting_time"],
                     spell_info["range"], spell_info["components"], spell_info["duration"]),
                )
            else:
                await db.execute(
                    """INSERT OR IGNORE INTO character_spells
                       (character_id, spell_key, spell_name, spell_level, source)
                       VALUES (?, ?, ?, 1, 'Найдено в приключении')""",
                    (character_id, spell_key, spell_key.replace("_", " ").title()),
                )
            await db.commit()
        finally:
            await db.close()


    async def _process_spell_keys(self, clean: str, character_id: str | None) -> tuple[str, list[str]]:
        """Обработать старый формат [SPELL: key] — поиск заклинания в приключении.

        Возвращает (clean, список_ключей).
        """
        saved = []
        for m in re.finditer(r'\[SPELL:\s*(\S+)\]', clean):
            spell_key = m.group(1)
            if spell_key.startswith("{"):
                continue  # уже обработано JSON-парсером выше

            spell_info = self._lookup_known_spell(spell_key) if character_id else None

            if character_id:
                await self._save_catalog_spell(character_id, spell_key, spell_info)

            saved.append(spell_key)
            name = spell_info["name"] if spell_info else spell_key.replace("_", " ").title()
            clean = clean.replace(m.group(0), f"*{name}*" if spell_info else spell_key, 1)

        return clean, saved


    async def _process_spell_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Вытащить [SPELL: key] или [SPELL: {json}] теги из ответа DM и сохранить заклинания.

        Два формата:
        - JSON — кастомные заклинания, созданные в диалоге (балансированный
          парсер скобок поддерживает любую вложенность);
        - ключ — свитки из каталога SPELLS_BY_CLASS («найдено в приключении»).
        """
        import json as _json

        saved = []
        clean = reply

        # 1. JSON-формат: [SPELL: {"name": "...", ...}]
        for tag, json_str in zip(*self._extract_spell_json_tags(reply)):
            replacement, name = await self._process_custom_spell_tag(reply, tag, json_str, character_id)
            saved.append(name)
            clean = clean.replace(tag, replacement, 1)

        # 2. Старый формат: [SPELL: key]
        clean, key_saved = await self._process_spell_keys(clean, character_id)
        saved.extend(key_saved)

        return clean, saved


    # ── _process_travel_tags ──

