"""Чат-сервис: история диалогов в SQLite + общение с ForgetAPI (DeepSeek v4 Flash)."""

import asyncio
import re
from datetime import datetime, timezone

from openai import APIError, AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimit

from app.config import POLZA_EXTRA_BODY, settings
from app.db import get_db
from app.exceptions import AIError, RateLimitError
from app.logger import logger
from app.models import ChatRequest, ChatResponse
from app.services.dice import _clamp_dice_modifier, _server_roll
from app.services.history import _load_character
from app.services.memory_service import (
    should_summarize_user, summarize_user_messages,
)
from app.services.prompts import _build_system_prompt
from app.services.tag_processor import TagProcessorMixin


class ChatService(TagProcessorMixin):
    """Персистентная история диалогов в SQLite + OpenAI-совместимый API.

    Tag-процессинг ([SPELL]/[ITEM]/[BREAK]/[XP] и др.) наследуется из
    TagProcessorMixin — единый дом этих методов в tag_processor/.
    """

    _bg_tasks: set[asyncio.Task] = set()
    _summarize_locks: dict[str, asyncio.Lock] = {}
    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI(
            base_url=settings.llm_api_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.api_timeout,
        )

    # ── Game State (persisted anti-drift) ──────────────────

    @staticmethod
    async def _run_game_state_update(
        user_id: str, character_id: str | None,
        sql: str, params: tuple
    ) -> None:
        """Общий хелпер для INSERT/UPDATE game_state с автоподменой автокреата пользователя."""
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, 'auto')",
                (user_id, user_id),
            )
            await db.execute(sql, params)
            await db.commit()
        finally:
            await db.close()

    @staticmethod
    async def _save_game_state(
        user_id: str, character_id: str | None,
        location: str = "", scene: str = "", weapon: str = "",
        phase: str = "", last_reply: str = "",
        current_world: str = "", nsfw_level: str = "",
        nsfw_last_styles: str = "[]",
    ) -> None:
        """Persist game state extracted from DM reply."""
        await ChatService._run_game_state_update(
            user_id, character_id,
            """INSERT INTO game_state (user_id, character_id, location, scene, weapon, phase, last_reply, current_world, nsfw_last_styles, nsfw_level, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, character_id) DO UPDATE SET
               location=CASE WHEN excluded.location != '' THEN excluded.location WHEN game_state.location != '' THEN game_state.location ELSE '' END,
               scene=CASE WHEN excluded.scene != '' THEN excluded.scene WHEN game_state.scene != '' THEN game_state.scene ELSE '' END,
               weapon=CASE WHEN excluded.weapon != '' THEN excluded.weapon WHEN game_state.weapon != '' THEN game_state.weapon ELSE '' END,
               phase=CASE WHEN excluded.phase != '' THEN excluded.phase WHEN game_state.phase != '' THEN game_state.phase ELSE 'exploration' END,
               last_reply=CASE WHEN excluded.last_reply != '' THEN excluded.last_reply WHEN game_state.last_reply != '' THEN game_state.last_reply ELSE '' END,
               current_world=CASE WHEN excluded.current_world != '' THEN excluded.current_world WHEN game_state.current_world != '' THEN game_state.current_world ELSE 'forgotten_realms' END,
               nsfw_level=CASE WHEN excluded.nsfw_level != '' THEN excluded.nsfw_level WHEN game_state.nsfw_level != '' THEN game_state.nsfw_level ELSE 'on' END,
               nsfw_last_styles=CASE WHEN excluded.nsfw_last_styles != '[]' THEN excluded.nsfw_last_styles ELSE COALESCE(game_state.nsfw_last_styles, '[]') END,
               updated_at=datetime('now')""",
            (user_id, character_id or "", location, scene, weapon, phase, last_reply, current_world, nsfw_last_styles, nsfw_level),
        )

    @staticmethod
    async def _get_game_state(user_id: str, character_id: str | None) -> dict:
        """Load last persisted game state."""
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT location, scene, weapon, phase, last_reply, updated_at, current_world, nsfw_level, nsfw_last_styles
                   FROM game_state WHERE user_id = ? AND character_id IS ?
                   ORDER BY updated_at DESC LIMIT 1""",
                (user_id, character_id or ""),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        finally:
            await db.close()
        return {}

    @staticmethod
    def _parse_state_tag(reply: str) -> dict:
        """Extract [STATE: ...] from DM reply (single-line; won't match across newlines)."""
        m = re.search(r'\[STATE:\s*([^\]\n]+)\]', reply)
        if not m:
            return {}
        state_str = m.group(1)
        result = {}
        for part in state_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    # ── Commands ─────────────────────────────────────────────

    async def _handle_command(
        self, user_id: str, character_id: str | None, msg: str
    ) -> ChatResponse:
        """Обработка команд: /travel, /assess, /nsfw (диспетчер)."""
        parts = msg.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/travel":
            return await self._cmd_travel(user_id, character_id, arg)
        if cmd == "/assess":
            return await self._cmd_assess(character_id, arg)
        if cmd == "/nsfw":
            return await self._cmd_nsfw(user_id, character_id, arg)

        return ChatResponse(
            reply=f"❓ Неизвестная команда: {cmd}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _cmd_travel(
        self, user_id: str, character_id: str | None, arg: str
    ) -> ChatResponse:
        """/travel list | /travel <world_key> — перемещение по Потоку миров."""
        from app.knowledge.worlds import FlowWalkMechanics, WORLD_TEMPLATES, flow_tier_name

        gs = await self._get_game_state(user_id, character_id)
        raw_world = gs.get("current_world", "") if gs else ""
        current_world = raw_world if raw_world else "forgotten_realms"

        if arg == "list":
            character = await _load_character(character_id) if character_id else None
            lvl = character.get("level", 1) if character else 1
            worlds = FlowWalkMechanics.list_reachable(current_world, lvl)
            if not worlds:
                return ChatResponse(reply="🌌 Миры не найдены.", timestamp=datetime.now(timezone.utc).isoformat())

            lines = [f"🌌 **Мультивселенная — Поток миров**\n_Ты на {flow_tier_name(WORLD_TEMPLATES[current_world].tier)} (тир {WORLD_TEMPLATES[current_world].tier})_\n"]
            for w in worlds:
                icon = "✅" if w["can_travel"] else "❌"
                lines.append(
                    f"{icon} **{w['name']}** — тир {w['tier']} ({w['direction']})\n"
                    f"   _Разница: {w['tier_diff']:+}. {w['detail']}_"
                )
            return ChatResponse(
                reply="\n\n".join(lines),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if arg:
            character = await _load_character(character_id) if character_id else None
            if not character:
                return ChatResponse(
                    reply="⚠️ Сначала создайте персонажа.",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            lvl = character["level"]
            ok, detail = FlowWalkMechanics.can_travel(current_world, arg, lvl)
            if not ok:
                return ChatResponse(
                    reply=f"❌ Нельзя переместиться в этот мир: {detail}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

            target = WORLD_TEMPLATES[arg]
            # Обновить current_world + СБРОСИТЬ локацию/сцену (новый мир!)
            await self._save_game_state(
                user_id, character_id,
                current_world=arg,
                location="", scene="", weapon="",
                last_reply=f"Персонаж переместился в {target.name}.",
            )
            # Гарантированно очищаем старую локацию (ON CONFLICT сохраняет непустые)
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE game_state SET location='', scene='', weapon='' WHERE user_id=? AND character_id IS ?",
                    (user_id, character_id or ""),
                )
                await db.commit()
            finally:
                await db.close()
            return ChatResponse(
                reply=(
                    f"🌀 Ты открываешь портал в Потоке...\n\n"
                    f"**{target.name}** — тир {target.tier}\n"
                    f"_{flow_tier_name(target.tier)}_\n"
                    f"Плотность магии: {target.magic_density}x\n\n"
                    f"{target.description}\n\n"
                    f"_Твоё следующее сообщение будет в новом мире. DM получит контекст автоматически._"
                ),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        return ChatResponse(
            reply="🌌 Используй `/travel list` чтобы увидеть доступные миры, или `/travel <мир>` чтобы переместиться.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _cmd_assess(self, character_id: str | None, arg: str) -> ChatResponse:
        """/assess <target> — считывание информации из инфосферы."""
        from app.knowledge.worlds import assess_target

        if not arg:
            return ChatResponse(
                reply="🔍 **Оценка** — используй `/assess <цель>` чтобы считать информацию из инфосферы.",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        character = await _load_character(character_id) if character_id else None
        int_val = character.get("stats", {}).get("int", 10) if character else 10
        import random
        d20 = random.randint(1, 20)
        # DC зависит от «силы» цели — для простоты 12
        target_dc = 12
        result = assess_target(int_val, d20, target_dc)

        lines = [
            f"🔍 **Оценка: {arg}**",
            f"🎲 d20 = {d20} + {(int_val - 10)//2} (ИНТ {int_val}) = {d20 + (int_val - 10)//2}",
            "",
            result.narrative,
        ]
        if result.backlash:
            lines.append(f"\n⚠️ **Откат:** {result.backlash}")
        if result.info:
            info_lines = [f"- {k}: {v}" for k, v in result.info.items() if v]
            lines.append("\n📊 **Информация:**\n" + "\n".join(info_lines))

        return ChatResponse(
            reply="\n".join(lines),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _cmd_nsfw(
        self, user_id: str, character_id: str | None, arg: str
    ) -> ChatResponse:
        """/nsfw off|mild|on|detail — уровень интимных сцен."""
        from app.knowledge.worlds import NSFW_DETAIL_LEVELS

        arg_lower = arg.lower()
        if arg_lower in NSFW_DETAIL_LEVELS:
            await self._save_game_state(
                user_id, character_id, nsfw_level=arg_lower,
            )
            return ChatResponse(
                reply=f"🔞 Уровень интимных сцен: **{arg_lower}** — {NSFW_DETAIL_LEVELS[arg_lower]}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        return ChatResponse(
            reply=f"🔞 Используй: `/nsfw off` / `mild` / `on` / `detail`\nТекущие уровни: {', '.join(NSFW_DETAIL_LEVELS.keys())}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ── DB helpers ──────────────────────────────────────────

    async def _save_message(
        self, user_id: str, role: str, content: str, character_id: str | None = None
    ) -> None:
        """Сохранить одно сообщение в БД."""
        db = await get_db()
        try:
            # Убедимся что пользователь существует
            await db.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, 'auto')",
                (user_id, user_id),
            )
            await db.execute(
                "INSERT INTO chat_history (user_id, character_id, role, content) VALUES (?, ?, ?, ?)",
                (user_id, character_id or "", role, content),
            )
            await db.commit()
        finally:
            await db.close()

    async def _load_history(
        self, user_id: str, character_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        """Загрузить последние N сообщений (самые новые, в хронологическом порядке)."""
        if limit is None:
            limit = settings.max_history_length * 2  # user+assistant pairs

        db = await get_db()
        try:
            # Subquery: DESC to get newest, then ASC for chronological order
            cursor = await db.execute(
                """SELECT role, content FROM (
                       SELECT id, role, content FROM chat_history
                       WHERE user_id = ? AND character_id IS ? AND role != 'system'
                       ORDER BY id DESC LIMIT ?
                   ) ORDER BY id ASC""",
                (user_id, character_id or "", limit),
            )
            rows = await cursor.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]
        finally:
            await db.close()

    # ── Core logic ─────────────────────────────────────────

    async def _get_history(
        self, user_id: str, character_id: str | None = None
    ) -> list[dict]:
        """Получить полную историю: system prompt + память + game_state + сообщения."""
        from app.services.memory_service import load_user_memories

        character = await _load_character(character_id) if character_id else None
        system_content = _build_system_prompt(character)

        # Inject long-term memory summaries (мем-палас)
        memories = await load_user_memories(user_id, character_id)
        if memories:
            system_content += "\n\n" + memories

        # Inject current game state as hard anchor
        gs = await self._get_game_state(user_id, character_id)
        if gs and (gs.get("location") or gs.get("scene")):
            system_content += (
                f"\n\n=== 📍 ТЕКУЩЕЕ СОСТОЯНИЕ (НЕ ПРОТИВОРЕЧЬ) ===\n"
                f"Локация: {gs.get('location', '?')}\n"
                f"Сцена: {gs.get('scene', '?')}\n"
                f"Оружие: {gs.get('weapon', 'none')}\n"
                f"Фаза: {gs.get('phase', 'exploration')}"
            )

        # Inject world context (multiverse)
        current_world = gs.get("current_world", "forgotten_realms") if gs else "forgotten_realms"
        from app.knowledge.worlds import FlowWalkMechanics, NSFW_NARRATIVE_STYLES, NSFW_STYLE_PROMPTS, NSFW_DETAIL_LEVELS
        world_ctx = FlowWalkMechanics.get_world_context(current_world)
        if "prompt" in world_ctx:
            system_content += "\n\n" + world_ctx["prompt"]

        # Inject NSFW settings
        nsfw_level = gs.get("nsfw_level", "on") if gs else "on"
        _nl = "\n"
        _style_list = _nl.join(f"{s}: {NSFW_STYLE_PROMPTS.get(s, '')}" for s in NSFW_NARRATIVE_STYLES)
        system_content += (
            f"\n\n=== 🔞 ИНТИМНАЯ БЛИЗОСТЬ ===\n"
            f"Уровень: {nsfw_level} — {NSFW_DETAIL_LEVELS.get(nsfw_level, NSFW_DETAIL_LEVELS['on'])}\n"
            f"Доступные стили повествования: {', '.join(NSFW_NARRATIVE_STYLES)}\n"
            f"НЕ ПОВТОРЯЙ один и тот же стиль два раза подряд. Чередуй.\n"
            f"Текущий стиль для следующей сцены выбирай случайно из доступных, исключая последний.\n"
            f"{_style_list}"
        )

        # Inject Assessment (Оценка) mechanics for DM awareness
        system_content += (
            "\n\n=== 🔍 УМЕНИЕ «ОЦЕНКА» (ASSESSMENT) ===\n"
            "Игрок может использовать /assess <цель> для считывания информации через инфосферу.\n"
            "Это НЕ магия — это врождённая способность разума. Работает в любом мире.\n"
            "Если игрок пишет «оцениваю», «изучаю цель», «считываю» — интерпретируй как Оценку.\n"
            "Бросок: d20 + мод.ИНТ против СЛ цели. Последствия зависят от ИНТ: "
            "от головной боли (ИНТ 8+) до инсульта и смерти (ИНТ 3).\n"
        )

        system_msg = {"role": "system", "content": system_content}
        messages = await self._load_history(user_id, character_id)
        return [system_msg] + messages

    @staticmethod
    def _trim_history(history: list[dict]) -> list[dict]:
        """Обрезать историю если слишком длинная (system prompt + N последних)."""
        max_msgs = settings.max_history_length + 1  # +1 = system prompt
        if len(history) <= max_msgs:
            return history
        return [history[0]] + history[-(max_msgs - 1) :]

    def _server_dice_roll(self, roll, character: dict | None) -> dict | None:
        """Серверный бросок кубиков (анти-чит): клиент шлёт только dice+modifier+label,
        результаты генерирует сервер; модификатор клампится по статам персонажа."""
        if not roll:
            return None
        mod = _clamp_dice_modifier(roll.modifier, character)
        try:
            res = _server_roll(list(roll.dice), mod, bool(roll.advantage), bool(roll.disadvantage))
        except ValueError:
            logger.warning("dice: невалидный размер кубика %s", getattr(roll, "dice", None))
            return None
        res["label"] = roll.label or ""
        return res

    def _build_dice_content(self, request: ChatRequest, state_anchor: str,
                            server_roll: dict | None = None) -> tuple[str, str]:
        """Форматировать сообщение игрока: текст + опционально бросок кубиков.

        Возвращает (content, user_msg_for_db) — контент для LLM и чистое
        сообщение для истории. Источник истины по броску — server_roll
        (серверные results/total/modifier); клиентские roll.results игнорируются.
        """
        content = request.message
        user_msg_for_db = request.message  # сохраняем чистое сообщение для истории
        if request.dice_roll:
            roll = request.dice_roll
            # Анти-чит: серверный бросок приоритетнее клиентских results
            if server_roll:
                dice = list(server_roll.get("dice", roll.dice))
                results = list(server_roll.get("results", []))
                modifier = int(server_roll.get("modifier", roll.modifier))
                total = int(server_roll["total"])
            else:
                dice = list(roll.dice)
                results = list(roll.results)
                modifier = roll.modifier
                total = sum(roll.results) + roll.modifier
            dice_str = "+".join(f"d{d}" for d in dice)
            results_str = ", ".join(str(r) for r in results)
            mod_str = (
                f" + {modifier}"
                if modifier > 0
                else (f" - {abs(modifier)}" if modifier < 0 else "")
            )
            label = (roll.label or "")
            action_hint = request.message.strip() if request.message else ""
            action_line = f"\n\nИгрок: «{action_hint}»" if action_hint else ""
            user_msg_for_db = f'🎲 {label}: {dice_str} = [{results_str}]{mod_str if mod_str else ""} = {total}{action_line}'  # для истории
            # Branch directive: combat vs skill check
            label_lower = label.lower()
            if any(k in label_lower for k in ("атак", "урон", "кд", "инициатив", "спасбросок")):
                directive = (
                    "[🎯 БОЙ: обработай ИМЕННО этот бросок. Не меняй локацию/оружие. "
                    "Соблюдай ПОРЯДОК БОЯ: атака→урон→эффект, потом ход врага.]"
                )
            else:
                directive = (
                    "[🎯 Заверши проверку навыка. Опиши успех/провал в ТОЙ ЖЕ сцене. "
                    "Не переходи в новую локацию, не меняй оружие. НЕ спрашивай «куда идёшь».]"
                )
            content = (
                f"{state_anchor}"
                f"{directive}\n\n"
                f"🎲 {label}: {dice_str} = [{results_str}]{mod_str if mod_str else ''} = **{total}**"
                f"{action_line}"
            )
        else:
            # Non-roll message: inject state anchor
            if state_anchor:
                content = state_anchor + content
        return content, user_msg_for_db

    async def handle_message(self, request: ChatRequest) -> ChatResponse:
        user_id = request.user_id or ""
        character_id = request.character_id

        # ── Команды мультивселенной и системы ──
        msg = request.message.strip()
        if msg.startswith("/"):
            return await self._handle_command(user_id, character_id, msg)

        # ── Загружаем persisted game state как якорь против дрифта ──
        gs = await self._get_game_state(user_id, character_id)
        if gs:
            state_anchor = f"[📍 СЕЙЧАС: {gs.get('location', 'неизвестно')}]\n"
            if gs.get("scene"):
                state_anchor += f"[🎬 СЦЕНА: {gs['scene']}]\n"
            if gs.get("weapon") and gs["weapon"] != "none":
                state_anchor += f"[⚔️ ОРУЖИЕ: {gs['weapon']}]\n"
        else:
            state_anchor = ""

        # Серверный бросок кубиков (анти-чит) + персонаж для клампа модификатора
        character = await _load_character(character_id) if character_id else None
        server_roll = self._server_dice_roll(request.dice_roll, character)

        # Форматируем сообщение (текст + опционально бросок кубиков)
        content, user_msg_for_db = self._build_dice_content(request, state_anchor, server_roll)

        # Загружаем историю из БД + system prompt
        history = await self._get_history(user_id, character_id)
        history.append({"role": "user", "content": content})
        history = self._trim_history(history)

        logger.info(
            "user=%s → ForgetAPI, history=%d msgs",
            user_id[:8],
            len(history),
        )

        try:
            response = await self.client.chat.completions.create(
                model=settings.model,
                messages=history,
                temperature=0.85,
                max_tokens=2000,
                presence_penalty=0.3,
                extra_body=POLZA_EXTRA_BODY,
            )
        except OpenAIRateLimit:
            logger.warning("ForgetAPI rate limit hit")
            raise RateLimitError("Превышен лимит API. Попробуйте через минуту.")
        except APIError as e:
            logger.error("ForgetAPI APIError: %s", e)
            raise AIError("Ошибка AI-сервиса. Попробуйте позже.")
        except Exception as e:
            logger.exception("Unexpected error")
            raise AIError(f"Неожиданная ошибка: {e}")

        reply = response.choices[0].message.content or ""
        clean_reply = await self._postprocess_reply(reply, user_id, character_id)

        try:
            await self._save_message(user_id, "user", user_msg_for_db, character_id)
            await self._save_message(user_id, "assistant", clean_reply, character_id)
        except Exception:
            logger.exception("History save failed — AI reply still delivered")

        # 🔥 Мем-палас: фоновая суммаризация (atomic lock acquire)
        lock = ChatService._summarize_locks.setdefault(user_id, asyncio.Lock())
        t = asyncio.create_task(self._maybe_summarize(user_id, character_id, lock))
        ChatService._bg_tasks.add(t)
        t.add_done_callback(ChatService._bg_tasks.discard)

        return ChatResponse(
            reply=clean_reply,
            timestamp=datetime.now(timezone.utc).isoformat(),
            dice_roll=server_roll,
        )
    async def _postprocess_reply(self, reply: str, user_id: str, character_id: str | None) -> str:
        """Пост-обработка ответа DM: тег-процессинг, strip служебных тегов, persist [STATE].

        Порядок тегов фиксирован: SPELL → ITEM → BREAK → XP.
        Безопасно: падение тег-процессинга логируется, сырой ответ всё равно дойдёт
        до игрока (AI-вызов не теряется).
        """
        # ── Tag processing (safe: failures logged, AI reply always reaches user) ──
        clean_reply = reply
        try:
            # Обработка [SPELL: key] тегов — авто-сохранение заклинаний
            clean_reply, _saved_spells = await self._process_spell_tags(clean_reply, character_id)

            # Обработка [ITEM: key] тегов — авто-выдача предметов
            clean_reply, _saved_items = await self._process_item_tags(clean_reply, character_id)

            # Обработка [BREAK: key] тегов — авто-удаление сломанных предметов
            clean_reply, _broken_items = await self._process_break_tags(clean_reply, character_id)

            # Обработка [XP: N] и [LEVEL_UP] тегов — авто-начисление опыта
            clean_reply, _xp_gained, _leveled_up = await self._process_xp_tags(clean_reply, character_id)

            # ── Persist game state from [STATE] tag ──
            state = self._parse_state_tag(clean_reply)
            if state:
                await self._save_game_state(
                    user_id, character_id,
                    location=state.get("location", ""),
                    scene=state.get("scene", ""),
                    weapon=state.get("weapon", ""),
                    phase=state.get("phase", ""),
                    last_reply=clean_reply,
                )
        except Exception:
            logger.exception("Tag processing failed — showing RAW reply to user (AI call NOT lost)")

        # Strip ALL system tags from reply shown to user (always, even after tag failure)
        clean_reply = re.sub(r'\n?\[STATE:[^\]\n]*\]\n?', '', clean_reply).strip()
        clean_reply = re.sub(r'\n?\[XP:\s*\d+\]\n?', '', clean_reply).strip()
        clean_reply = re.sub(r'\n?\[LEVEL_UP\]\n?', '', clean_reply).strip()
        clean_reply = re.sub(r'\n?\[SPELL:[^\]]+\]\n?', '', clean_reply).strip()
        clean_reply = re.sub(r'\n?\[ITEM:[^\]]+\]\n?', '', clean_reply).strip()
        clean_reply = re.sub(r'\n?\[BREAK:[^\]]+\]\n?', '', clean_reply).strip()
        return clean_reply

    async def _process_spell_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Делегат в TagProcessorMixin (items.py) — JSON и ключевые форматы тегов."""
        return await super()._process_spell_tags(reply, character_id)

    async def _process_item_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Делегат в TagProcessorMixin (items.py) — выдача предметов с дедупом."""
        return await super()._process_item_tags(reply, character_id)

    async def _process_break_tags(self, reply: str, character_id: str | None) -> tuple[str, list[str]]:
        """Делегат в TagProcessorMixin (travel.py) — удаление сломанных предметов."""
        return await super()._process_break_tags(reply, character_id)

    async def _process_xp_tags(self, reply: str, character_id: str | None) -> tuple[str, int, bool]:
        """Делегат в TagProcessorMixin (progression.py) — парсинг XP-тегов + применение уровней."""
        return await super()._process_xp_tags(reply, character_id)


    # ── stream_message ──

    async def stream_message(self, request: "ChatRequest"):
        """Стриминговый вариант handle_message: отдаёт чанки текста по мере
        генерации модели (SSE), а в конце — полный ChatResponse после
        тег-процессинга. Генератор: {"type": "delta", "text": ...} / {"type": "done", "response": {...}}"""
        user_id = request.user_id
        character_id = request.character_id

        # ── Команды мультивселенной и системы ──
        msg = request.message.strip()
        if msg.startswith("/"):
            resp = await self._handle_command(user_id, character_id, msg)
            yield {"type": "delta", "text": resp.reply}
            yield {"type": "done", "response": resp.model_dump(mode="json")}
            return

        # ── Загружаем persisted game state как якорь против дрифта ──
        gs = await self._get_game_state(user_id, character_id)
        if gs:
            state_anchor = f"[📍 СЕЙЧАС: {gs.get('location', 'неизвестно')}]\n"
            if gs.get("scene"):
                state_anchor += f"[🎬 СЦЕНА: {gs['scene']}]\n"
            if gs.get("weapon") and gs["weapon"] != "none":
                state_anchor += f"[⚔️ ОРУЖИЕ: {gs['weapon']}]\n"
        else:
            state_anchor = ""

        # Серверный бросок кубиков (анти-чит) + персонаж для клампа модификатора
        character = await _load_character(character_id) if character_id else None
        server_roll = self._server_dice_roll(request.dice_roll, character)

        # Форматируем сообщение (текст + опционально бросок кубиков)
        content, user_msg_for_db = self._build_dice_content(request, state_anchor, server_roll)

        # Загружаем историю из БД + system prompt
        history = await self._get_history(user_id, character_id)
        history.append({"role": "user", "content": content})
        history = self._trim_history(history)

        logger.info("user=%s → ForgetAPI STREAM, history=%d msgs", user_id[:8], len(history))

        full = ""
        pending = ""
        TAG_PATTERN = r"\n?\[(?:STATE|XP|LEVEL_UP|SPELL|ITEM|BREAK|APPEARANCE|NPC|NPC_STATE|HP|REVIVE|QUEST|KARMA|SHOP|SELL|COMPANION|COMPANION_STATE):?[^\]\n]*\]\n?"

        # ── Открытие стрима с ретраем (rate limit прилетает на первом чанке) ──
        _MAX_ATTEMPTS = 3
        _delivered = False
        for _attempt in range(_MAX_ATTEMPTS):
            full = ""
            pending = ""
            try:
                stream = await self.client.chat.completions.create(
                    model=settings.model,
                    messages=history,
                    temperature=0.85,
                    max_tokens=6000,
                    presence_penalty=0.3,
                    extra_body=POLZA_EXTRA_BODY,
                    stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    piece = (delta.content or "") if delta else ""
                    if not piece:
                        continue
                    full += piece
                    pending += piece
                    last_open = pending.rfind("[")
                    if last_open != -1:
                        if "]" not in pending[last_open:]:
                            safe, pending = pending[:last_open], pending[last_open:]
                        else:
                            safe, pending = pending, ""
                    else:
                        safe, pending = pending, ""
                    if safe:
                        safe = re.sub(TAG_PATTERN, "", safe)
                        if safe:
                            _delivered = True
                            yield {"type": "delta", "text": safe}
                break
            except (OpenAIRateLimit, APIError) as e:
                if _delivered or _attempt == _MAX_ATTEMPTS - 1:
                    logger.error("ForgetAPI rate/API error (stream): %s", e)
                    raise AIError("Сервис перегружен, повторите через несколько секунд.")
                _wait = 2 * (_attempt + 1)
                logger.warning("ForgetAPI rate limit (stream, попытка %d/%d), пауза %ds",
                               _attempt + 1, _MAX_ATTEMPTS, _wait)
                await asyncio.sleep(_wait)
            except Exception as e:
                logger.exception("Stream error")
                raise AIError(f"Ошибка стриминга: {e}")

        # Финал: остаток pending
        if pending:
            pending_clean = re.sub(TAG_PATTERN, "", pending)
            if pending_clean:
                yield {"type": "delta", "text": pending_clean}

        # Полный тег-процессинг через существующий _postprocess_reply
        try:
            clean_reply = await self._postprocess_reply(full, user_id, character_id)
            # Save to history
            try:
                await self._save_message(user_id, "user", user_msg_for_db, character_id)
                await self._save_message(user_id, "assistant", clean_reply, character_id)
            except Exception:
                logger.exception("History save failed — AI reply still delivered")
            from app.models import ChatResponse as _CR
            resp = _CR(
                reply=clean_reply,
                timestamp=datetime.now(timezone.utc).isoformat(),
                dice_roll=server_roll,
            )
        except Exception:
            logger.exception("postprocess failed in stream — sending raw")
            from app.models import ChatResponse as _CR
            resp = _CR(
                reply=re.sub(TAG_PATTERN, "", full).strip(),
                timestamp=datetime.now(timezone.utc).isoformat(),
                dice_roll=server_roll,
            )
        yield {"type": "done", "response": resp.model_dump(mode="json")}


    async def _maybe_summarize(self, user_id: str, character_id: str | None = None,
                             lock: asyncio.Lock | None = None) -> None:
        """Фоновая суммаризация истории (мем-палас). lock передаётся из handle_message."""
        if lock is None:
            lock = ChatService._summarize_locks.get(user_id)
            if lock is None:
                return
        try:
            async with lock:
                if await should_summarize_user(user_id, character_id):
                    await summarize_user_messages(user_id, character_id)
                    logger.info("memory summarized for user=%s", user_id[:8])
        except Exception:
            logger.exception("memory summarization failed")

    async def clear_history(self, user_id: str) -> None:
        """Удалить всю историю диалогов пользователя."""
        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM chat_history WHERE user_id = ?", (user_id,)
            )
            await db.execute(
                "DELETE FROM game_state WHERE user_id = ?", (user_id,)
            )
            await db.execute(
                "DELETE FROM user_memory WHERE user_id = ?", (user_id,)
            )
            await db.commit()
            logger.info("history cleared for user=%s", user_id[:8])
        finally:
            await db.close()


chat_service = ChatService()
