import re
import time

from app.db import get_db
from app.logger import logger
# Импорт модульных переменных из base.py (XP-транзакции)
from app.services.tag_processor.base import _xp_transactions

class ProgressionMixin:
    """Прогрессия: XP-фолбэк, XP-теги, карма, квесты."""

    """Миксин с методами обработки тегов DM."""

    # gold_transactions на модульном уровне (см. _gold_transactions выше)

    _XP_EVENT_MARKERS = {
        "kill": ["убиваешь", "повержен", "падает замертво", "расправляешься", "обезглавливаешь",
                 "уничтожаешь", "пронзаешь", "сокрушаешь", "отправляешь на тот свет", "мёртв",
                 "мертва", "мертво", "умирает", "падает мёртвым"],
        "save": ["спасаешь", "вытаскиваешь", "защищаешь", "прикрываешь", "отводишь удар"],
        "quest": ["задание выполнено", "квест завершён", "поручение выполнено", "ты справился",
                  "миссия выполнена", "заказ выполнен"],
        "seduce": ["соблазняешь", "целуешь", "раздеваешь", "овладеваешь", "ложишься в постель"],
        "pact": ["сделку принял", "сделка заключена", "договор заключён", "клятва скреплена",
                 "скреплена кровью", "продаёшь душу", "продал душу", "душа достанется",
                 "условия сделки", "заключаешь сделку", "принимает сделку", "сделка скреплена"],
    }
    
    # Классификация врагов по XP (босс, сильный, моб)
    _XP_FALLBACK_RULES = [
        (400, "boss", ["дракон", "лич", "демон", "архидемон", "архимаг", "король", "лорд", "владыка"]),
        (150, "strong", ["рыцарь", "воин", "маг", "чародей", "огр", "тролль", "вампир", "оборотень"]),
        (50, "mob", ["гоблин", "кобольд", "зомби", "скелет", "разбойник", "бандит", "волк", "крыса"]),
    ]

    # ── _appearance_semantically_same ──


    async def _detect_xp_fallback(self, reply: str, user_message: str, character_id: str | None = None) -> int:
        """Начислить базовый XP если модель НЕ выдала [XP: N], но в ответе DM
        есть явные маркеры завершённого события. Возвращает 0 если события нет.
        Имеет rate limit: макс 1000 XP за 10 минут."""
        if character_id:
            now = time.time()
            tx_list = _xp_transactions.setdefault(character_id, [])
            # чистим старые записи (>10 мин)
            tx_list[:] = [(t, x) for t, x in tx_list if t >= now - 600]
            total = sum(x for _, x in tx_list)
            if total >= 1000:
                logger.debug("XP rate limit hit for %s: %d/1000", character_id, total)
                return 0
        low = reply.lower()

        # Квест (приоритет — точный маркер)
        if any(m in low for m in self._XP_EVENT_MARKERS["quest"]):
            if "основн" in low or "главн" in low or "сюжет" in low:
                return 500
            return 150

        # Спасение NPC
        if any(m in low for m in self._XP_EVENT_MARKERS["save"]):
            return 100

        # Сделка / договор с сущностью (демон, фея, бог, дух и т.п.)
        if any(m in low for m in self._XP_EVENT_MARKERS["pact"]):
            # Продажа души — экстремальная ставка, выше обычной сделки
            if "душ" in low:
                return 300
            return 150

        # Соблазнение / интим
        if any(m in low for m in self._XP_EVENT_MARKERS["seduce"]):
            return 100

        # Убийство — определяем тип врага
        if any(m in low for m in self._XP_EVENT_MARKERS["kill"]):
            # Босс
            if any(m in low for m in self._XP_FALLBACK_RULES[0][2]):
                return 400
            # Сильный враг
            if any(m in low for m in self._XP_FALLBACK_RULES[1][2]):
                return 150
            # Моб
            if any(m in low for m in self._XP_FALLBACK_RULES[2][2]):
                return 50
            # Неопознанный враг — минимум
            return 30

        return 0


    # ── _extract_npc_tag_from_reply ──


    async def _get_quests_for_prompt(self, character_id: str | None) -> str:
        """Журнал квестов персонажа для system-промпта DM."""
        if not character_id:
            return ""
        db = await get_db()
        try:
            cur = await db.execute(
                """SELECT title, description, status FROM quests
                   WHERE character_id = ?
                   ORDER BY (status = 'active') DESC, updated_at DESC LIMIT 10""",
                (character_id,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()
        if not rows:
            return ""
        parts = []
        for r in rows:
            icon = {"active": "📜", "completed": "✅", "failed": "❌"}.get(r["status"], "📜")
            title = (r["title"] or "").strip()
            desc = (r["description"] or "").strip()
            line = f"- {icon} {title}"
            if r["status"] != "active":
                line += f" ({r['status']})"
            if desc:
                line += f" — {desc[:120]}"
            parts.append(line)
        return "\n".join(parts)


    # ── _mark_viewed ──


    async def _process_karma_tags(self, reply: str, character_id: str | None) -> tuple[str, int | None]:
        """Обработать [KARMA: +/-N] — изменение кармы/репутации персонажа.

        Карма копится от −100 (злодей) до +100 (герой). Бэкенд зажимает в эти рамки.
        Возвращает (clean_reply, karma_after) — карму после изменения (None если тега нет).
        """
        m = re.search(r'\[KARMA:\s*([+-]?\d+)\]', reply)
        if not m:
            return reply, None
        delta = int(m.group(1))
        clean = re.sub(r'\n?\[KARMA:\s*[+-]?\d+\]\n?', '', reply).strip()

        karma_after = None
        if character_id:
            db = await get_db()
            try:
                cur = await db.execute("SELECT karma FROM characters WHERE id = ?", (character_id,))
                row = await cur.fetchone()
                if row:
                    karma_after = max(-100, min(100, (row["karma"] or 0) + delta))
                    await db.execute(
                        "UPDATE characters SET karma = ?, updated_at = datetime('now') WHERE id = ?",
                        (karma_after, character_id),
                    )
                    await db.commit()
                    logger.info("⚖️ KARMA char=%s %+d → %d", character_id[:12], delta, karma_after)
                else:
                    logger.warning("[KARMA] character %s not found", character_id)
            except Exception:
                logger.exception("Karma tag processing failed")
            finally:
                await db.close()

        return clean, karma_after


    # ── _process_npc_state_tags ──


    async def _process_quest_tags(self, reply: str, character_id: str | None) -> tuple[str, int]:
        """Обработать [QUEST: ключ|название|статус|описание] — журнал квестов.

        Статусы: active/completed/failed. Ключ — уникальный ид квеста (короткий, латиницей).
        Обновление: тот же ключ + активный статус → обновляем название/описание.
        Возвращает (clean_reply, quests_count) — количество квестов в журнале после обработки.
        """
        pattern = re.compile(r'\[QUEST:\s*([^|\]]+)\|([^|\]]+)\|(active|completed|failed)\|([^\]]*)\]')
        clean = reply
        quests_count = 0
        if character_id:
            for m in pattern.finditer(reply):
                q_key = m.group(1).strip()
                q_title = m.group(2).strip()
                q_status = m.group(3).strip()
                q_desc = m.group(4).strip()
                db = await get_db()
                try:
                    cur = await db.execute(
                        "SELECT id, status FROM quests WHERE character_id = ? AND quest_key = ?",
                        (character_id, q_key),
                    )
                    row = await cur.fetchone()
                    if row:
                        await db.execute(
                            """UPDATE quests SET title = ?, description = ?, status = ?,
                               updated_at = datetime('now') WHERE id = ?""",
                            (q_title, q_desc, q_status, row["id"]),
                        )
                    else:
                        await db.execute(
                            """INSERT INTO quests (character_id, quest_key, title, description, status)
                               VALUES (?, ?, ?, ?, ?)""",
                            (character_id, q_key, q_title, q_desc, q_status),
                        )
                    await db.commit()
                    logger.info("📜 QUEST char=%s key=%s status=%s", character_id[:12], q_key, q_status)
                except Exception:
                    logger.exception("Quest tag processing failed")
                finally:
                    await db.close()
            clean = re.sub(pattern, '', clean).strip()
            # Считаем активные квесты для подсказки DM
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT COUNT(*) AS n FROM quests WHERE character_id = ? AND status = 'active'",
                    (character_id,),
                )
                row = await cur.fetchone()
                quests_count = row["n"] if row else 0
            finally:
                await db.close()
        return clean, quests_count


    # ── _process_rest_tags ──


    async def _process_xp_tags(self, reply: str, character_id: str | None) -> tuple[str, int, bool]:
        """Вытащить [XP: N] и [LEVEL_UP] теги, начислить опыт, сигналить о левелапе.

        Уровень НЕ повышается автоматически: при достижении порога возвращаем
        leveled_up=True, а клиент открывает экран повышения уровня (LevelUpScreen),
        где игрок сам выбирает: повысить текущий класс или взять мультикласс.
        Само повышение делает POST /characters/{id}/level-up (см. characters.py).
        """
        import re
        from app.knowledge.srd_rules import XP_THRESHOLDS, check_level_up

        xp_gained = 0
        leveled_up = False
        clean = reply

        # 1. Ищем [XP: N]
        for m in re.finditer(r'\[XP:\s*(\d+)\]', reply):
            xp_gained += int(m.group(1))
            clean = clean.replace(m.group(0), "", 1)

        # 2. Ищем [LEVEL_UP]
        has_level_up = bool(re.search(r'\[LEVEL_UP\]', reply))
        clean = re.sub(r'\n?\[LEVEL_UP\]\n?', '', clean).strip()

        # 3. Fallback: модель не дала [XP: N], но событие явно завершилось —
        #    бэкенд начисляет базовый XP сам (детерминированно, без LLM).
        if xp_gained == 0 and character_id:
            fallback_xp = await self._detect_xp_fallback(clean, "", character_id)
            if fallback_xp > 0:
                                xp_gained = fallback_xp
                                if character_id:
                                    _xp_transactions.setdefault(character_id, []).append((time.time(), fallback_xp))
                                logger.info(
                    "XP fallback (модель не выдала [XP]): char=%s +%d XP",
                    character_id[:12], fallback_xp,
                )

        if character_id and (xp_gained > 0 or has_level_up):
            db = await get_db()
            try:
                cursor = await db.execute(
                    "SELECT xp, level FROM characters WHERE id = ?",
                    (character_id,),
                )
                row = await cursor.fetchone()
                if row:
                    current_xp = row["xp"]
                    current_level = row["level"]
                    new_xp = current_xp + xp_gained

                    # Начисляем XP всегда
                    await db.execute(
                        "UPDATE characters SET xp = ? WHERE id = ?",
                        (new_xp, character_id),
                    )

                    # Левелап: [LEVEL_UP] форс или порог пройден
                    if has_level_up or check_level_up(current_level, new_xp):
                        leveled_up = True
                        logger.info("LEVEL_UP ready: char=%s lvl=%d xp=%d (клиент откроет экран)",
                                    character_id[:12], current_level, new_xp)

                    await db.commit()
            finally:
                await db.close()

        return clean, xp_gained, leveled_up


    # ── _save_npc_entry ──


