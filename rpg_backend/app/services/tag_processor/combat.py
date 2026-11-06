import json
import re
from datetime import datetime, timezone

from app.db import get_db
from app.logger import logger
# Импорт модульных функций из base.py (HP-транзакции)
from app.services.tag_processor.base import process_hp_tags

class CombatMixin:
    """Бой: HP-теги, инициатива, конец боя, отдых, ревайв."""

    async def _save_combat_state(
        self, entries: list[dict], user_id: str | None, character_id: str | None,
        *, round_no: int = 1, log_label: str,
    ) -> None:
        """Общая запись боевого порядка в game_state.combat.

        Используется _detect_combat_from_text (fallback, round=1) и
        _process_init_tags ([INIT], round+1). Ошибки БД залогируются, не роняют ход.
        """
        db = await get_db()
        try:
            combat_json = json.dumps(
                {"order": entries, "round": round_no, "started": datetime.now(timezone.utc).isoformat()},
                ensure_ascii=False,
            )
            await db.execute(
                "UPDATE game_state SET combat = ?, updated_at = datetime('now') WHERE user_id = ? AND character_id IS ?",
                (combat_json, user_id or "", character_id),
            )
            await db.commit()
            logger.info("⚔️ %s char=%s round=%d order=%s", log_label, character_id[:12], round_no,
                        ", ".join(f"{e['name']}={e['value']}" for e in entries))
        except Exception:
            logger.exception("Combat state save failed (%s)", log_label)
        finally:
            await db.close()

    async def _detect_combat_from_text(self, reply: str, character_id: str | None, user_id: str | None = None) -> bool:
        """Fallback-детектор боя: модель объявила порядок ходов текстом без [INIT].

        Ищем паттерны:
          «Порядок ходов: 1. Имя — 20» / «1. Имя — 20» / «Имя (20)» / «Имя: 20»
        Собираем участников и сохраняем combat (раунд 1). Ничего не режем из reply —
        только пишем в game_state, чтобы state_anchor показывал «БОЙ ИДЁТ».
        """
        text = reply
        # Убираем markdown-жирность и лишние артефакты для парсинга
        probe = re.sub(r"\*\*|\*", "", text)

        # Паттерн: строки вида "1. Имя — 20", "1. Имя (20)", "Имя: 20", "Имя — 20"
        entry_re = re.compile(
            r"(?:^|\n)\s*(?:\d+[.)]\s*)?(?P<name>[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z0-9' \-]{1,40}?)\s*"
            r"(?:[—–-]\s*|\:\s*|\(\s*)(?P<val>\d{1,3})\s*\)?",
            re.MULTILINE,
        )
        # Ограничиваем поиск: ищем только вблизи слов про порядок/ход/инициативу
        if not re.search(r"порядок ходов|инициатив|твой ход|действуешь первым|первым ход", text.lower()):
            return False

        entries: list[dict] = []
        for m in entry_re.finditer(probe):
            name = m.group("name").strip().strip(".").strip()
            val = int(m.group("val"))
            if not name or val <= 0 or val > 1000:
                continue
            # «Ты» → имя персонажа из БД (не знаем его здесь — оставляем как есть)
            if name.lower() in ("ты", "вы", "герой", "плут", "воин", "маг", "жрец"):
                name = "Игрок"
            # Пропускаем мусорные строки (брось, кд, атака и т.п.)
            if any(w in name.lower() for w in ("брось", "атака", "урон", "кд", "спасбросок", "порядок")):
                continue
            if len(name) > 40:
                continue
            if any(e["name"] == name for e in entries):
                continue
            entries.append({"name": name, "value": val})

        # Нужно минимум 2 участника с числами — иначе не бой
        if len(entries) < 2:
            return False

        entries.sort(key=lambda e: e["value"], reverse=True)

        if character_id:
            await self._save_combat_state(
                entries, user_id, character_id,
                round_no=1, log_label="COMBAT-DETECTED (fallback, без [INIT])",
            )

        return True


    # ── _detect_xp_fallback ──


    async def _process_combat_end_tags(self, reply: str, character_id: str | None, user_id: str | None = None) -> tuple[str, bool]:
        """Обработать [COMBAT_END] — завершение боя, сброс инициативы."""
        clean = re.sub(r'\[COMBAT_END\]', '', reply).strip()
        ended = bool(re.search(r'\[COMBAT_END\]', reply))
        if ended and character_id:
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE game_state SET combat = '{}', updated_at = datetime('now') WHERE user_id = ? AND character_id IS ?",
                    (user_id or "", character_id),
                )
                await db.commit()
                logger.info("🏁 COMBAT_END char=%s — бой завершён", character_id[:12])
            except Exception:
                logger.exception("Combat end tag processing failed")
            finally:
                await db.close()
        return clean, ended


    # ── _process_companion_state_tags ──


    async def _process_hp_tags(self, reply: str, character_id: str | None) -> tuple[str, int | None, int | None, bool]:
        """Тонкий враппер над модульной process_hp_tags."""
        return await process_hp_tags(reply, character_id)


    # ── _process_init_tags ──

    @staticmethod
    def _parse_init_entries(raw: str) -> list[dict]:
        """Разобрать тело [INIT: имя=знач, ...] → участники (сортировка на вызывающем)."""
        entries: list[dict] = []
        for part in raw.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, _, val = part.partition("=")
            name = name.strip().strip("*").strip()
            try:
                val_int = int(float(val.strip()))
            except ValueError:
                continue
            if name:
                entries.append({"name": name, "value": val_int})
        return entries

    async def _next_combat_round(self, user_id: str | None, character_id: str | None) -> int:
        """Прочитать текущий раунд из game_state.combat и вернуть следующий."""
        db = await get_db()
        round_no = 1
        try:
            cur = await db.execute(
                "SELECT combat FROM game_state WHERE user_id = ? AND character_id IS ? ORDER BY updated_at DESC LIMIT 1",
                (user_id or "", character_id),
            )
            row = await cur.fetchone()
            if row and row["combat"]:
                try:
                    old = json.loads(row["combat"]) if row["combat"] else {}
                    if old.get("round"):
                        round_no = int(old["round"]) + 1
                except Exception:
                    pass
        finally:
            await db.close()
        return round_no

    async def _process_init_tags(self, reply: str, character_id: str | None, user_id: str | None = None) -> tuple[str, bool]:
        """Обработать [INIT: имя=значение, имя2=значение2] — порядок ходов в бою.

        Парсит участников с инициативой (число), сортирует по убыванию,
        сохраняет в game_state.combat (JSON: order, round). Если бой уже шёл —
        обновляет порядок. Возвращает (clean_reply, combat_active).
        """
        m = re.search(r'\[INIT:\s*([^\]]+)\]', reply)
        if not m:
            return reply, False
        entries = self._parse_init_entries(m.group(1))
        if not entries:
            return reply, False
        entries.sort(key=lambda e: e["value"], reverse=True)

        clean = re.sub(r'\[INIT:\s*[^\]]+\]', '', reply, count=1).strip()

        if character_id:
            round_no = await self._next_combat_round(user_id, character_id)
            await self._save_combat_state(entries, user_id, character_id, round_no=round_no, log_label="INIT")

        return clean, True


    # ── _process_item_tags ──


    async def _process_rest_tags(self, reply: str, character_id: str | None, user_id: str | None = None) -> tuple[str, str | None]:
        """Обработать [REST: short|long] — короткий/длинный отдых.

        Короткий: +25% hp_max (хитдайсы). Длинный: полное HP + сброс боя.
        Возвращает (clean_reply, rest_type).
        """
        m = re.search(r'\[REST:\s*(short|long)\]', reply)
        if not m:
            return reply, None
        rest_type = m.group(1)
        clean = re.sub(r'\[REST:\s*(short|long)\]', '', reply).strip()

        if character_id:
            db = await get_db()
            try:
                cur = await db.execute("SELECT hp_max, hp_current FROM characters WHERE id = ?", (character_id,))
                row = await cur.fetchone()
                if row:
                    hp_max = row["hp_max"] or 10
                    hp_cur = row["hp_current"] or 0
                    if rest_type == "long":
                        new_hp = hp_max
                        # Длинный отдых сбрасывает бой (нельзя отдыхать в бою)
                        await db.execute(
                            "UPDATE game_state SET combat = '{}', updated_at = datetime('now') WHERE user_id = ? AND character_id IS ?",
                            (user_id or "", character_id),
                        )
                        logger.info("😴 REST long char=%s HP %d→%d (полное восстановление)", character_id[:12], hp_cur, new_hp)
                    else:
                        heal = max(1, hp_max // 4)  # 25% максимума (1 хитдайс)
                        new_hp = min(hp_max, hp_cur + heal)
                        logger.info("😴 REST short char=%s HP %d→%d (+%d)", character_id[:12], hp_cur, new_hp, heal)
                    await db.execute(
                        "UPDATE characters SET hp_current = ?, updated_at = datetime('now') WHERE id = ?",
                        (new_hp, character_id),
                    )
                    await db.commit()
            except Exception:
                logger.exception("Rest tag processing failed")
            finally:
                await db.close()

        return clean, rest_type


    # ── _process_revive_tags ──


    async def _process_revive_tags(self, reply: str, character_id: str | None) -> tuple[str, bool]:
        """Обработать [REVIVE] — воскрешение персонажа после смерти.

        Возвращает (clean_reply, revived): revived=True если персонаж воскрешён.
        """
        clean = re.sub(r'\n?\[REVIVE\]\n?', '', reply).strip()
        revived = bool(re.search(r'\[REVIVE\]', reply))
        if revived and character_id:
            db = await get_db()
            try:
                cur = await db.execute("SELECT hp_max FROM characters WHERE id = ?", (character_id,))
                row = await cur.fetchone()
                if row:
                    hp_max = row["hp_max"] or 10
                    await db.execute(
                        "UPDATE characters SET hp_current = ?, is_dead = 0, updated_at = datetime('now') WHERE id = ?",
                        (max(1, hp_max // 2), character_id),
                    )
                    await db.commit()
                    logger.info("✨ REVIVE char=%s — персонаж воскрешён (HP=%d)", character_id[:12], max(1, hp_max // 2))
            except Exception:
                logger.exception("Revive tag processing failed")
            finally:
                await db.close()
        return clean, revived


    # ── _process_shop_tags ──


