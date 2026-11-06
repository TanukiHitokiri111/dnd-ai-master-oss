"""Миксин обработки тегов: NPC: поиск, пул, состояние."""
import re

from app.config import settings, POLZA_EXTRA_BODY
from app.db import get_db
from app.logger import logger
from app.services.image_pool import image_pool_size, pick_unviewed_from_pool, save_npc_entry
from app.services import tag_db
from app.services.tag_processor.base import NPC_POOL_MIN, translate_appearance_prompt_en


def _parse_npc_tag_payload(raw: str) -> tuple[str | None, str]:
    """[NPC: имя|описание] → (npc_name, appearance); имя отделено '|'. """
    if "|" in raw:
        name_part, appearance = raw.split("|", 1)
        return (name_part.strip() or None), appearance.strip()
    return None, raw


class NpcMixin:
    """NPC: поиск по имени, пул картинок, реестр состояний."""

    async def _build_npc_prompt_en(self, npc_name: str | None, appearance: str, old_appearance: str | None = None) -> str:
        """Перевести описание NPC в детальный англ. промпт для image-модели.

        Единственная условная ветка — сборка рус. запроса; сам вызов LLM и
        фолбэк линейны, CC=3: разделять дальше нечего.
        """
        ru = (f"Имя NPC: {npc_name}. " if npc_name else "")
        if old_appearance:
            ru += f" Раньше он выглядел так: {old_appearance}. Теперь: {appearance}."
        else:
            ru += f" Внешность: {appearance}."

        return await translate_appearance_prompt_en(
            self.client, ru,
            system_prompt=self._npc_prompt_system_text(),
            context_label="NPC",
        )

    @staticmethod
    def _npc_prompt_system_text() -> str:
        """System-промпт для перевода внешности NPC в англ. промпт image-модели."""
        return (
            "You convert Russian D&D NPC appearance descriptions into "
            "detailed English image-generation prompts. Output ONLY the English "
            "prompt, no preamble, no quotes. Structure: "
            "'Fantasy portrait of {NPC name if known}, {key physical traits: "
            "race, build, face, skin, eyes, hair, scars/tattoos, distinctive "
            "marks, clothing, weapons}. Style: photorealistic, realistic, "
            "cinematic lighting, detailed face, lifelike skin texture, "
            "waist-up. No watermark, no text, "
            "no artist signature.'"
        )

    async def _generate_anon_npc_image(self, npc_name: str | None, appearance: str) -> str | None:
        """Сгенерировать картинку для безымянного NPC."""
        prompt = await self._build_npc_prompt_en(npc_name=npc_name, appearance=appearance)
        url = await self._generate_appearance_image(prompt)
        if url:
            logger.info("🖼️ NPC image generated (anon) url=%s", url)
        else:
            logger.warning("NPC image: both providers failed (anon)")
        return url

    @staticmethod
    def _load_full_npcs_sync(rows) -> list:
        """Оставить только записи с описанием И картинкой (полноценные NPC)."""
        return [
            r for r in rows
            if ((r["appearance"] or "").strip() and (r["appearance_url"] or "").strip())
        ]

    def _format_npc_listing(self, known: list) -> str:
        """Текстовый список известных NPC для LLM-сравнения."""
        return "\n".join(
            f"- Имя: {r['npc_name'] or '(безымянный)'} | Внешность: {r['appearance'][:400]}"
            for r in known
        )

    async def _ask_llm_same_npc(self, known_text: str, new_label: str) -> str | None:
        """Спросить LLM: это тот же NPC? Возвращает ответ модели или None при сбое."""
        try:
            resp = await self.client.chat.completions.create(
                model=settings.appearance_prompt_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты определяешь, является ли NPC из нового тега тем же самым, "
                            "что игрок уже видел раньше. Игрок может называть знакомого NPC "
                            "по-другому или обобщённо (тот же торговец, тот же охотник, снова "
                            "вижу его). Сравни ВНЕШНОСТЬ и роль NPC. Ответь СТРОГО ОДНИМ СЛОВОМ: "
                            "1) если это ТОТ ЖЕ NPC — ответь его ТОЧНЫМ именем из списка "
                            "(одно слово или фразой из списка, без пояснений, без кавычек); "
                            "2) если это НОВЫЙ NPC — ответь ровно: НОВЫЙ. "
                            "Больше ничего не пиши."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"ИЗВЕСТНЫЕ ИГРОКУ NPC:\n{known_text}\n\n"
                            f"НОВЫЙ ТЕГ:\n{new_label}"
                        ),
                    },
                ],
                max_tokens=150,
                temperature=0,
                extra_body=POLZA_EXTRA_BODY,
            )
            msg = resp.choices[0].message
            answer = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
            logger.info("NPC same check: %r", answer)
            return answer or None
        except Exception:
            logger.exception("NPC same check failed, treating as new")
            return None

    def _match_known_by_answer(self, known: list, answer: str | None) -> tuple[str, object] | None:
        """Сопоставить ответ LLM со списком известных NPC.

        Подстрочный матч имени без регистра; фолбэк — единственный кандидат
        (модель не сказала «НОВЫЙ»).
        """
        if not answer or answer.upper() == "НОВЫЙ":
            return None
        ans_low = answer.lower()
        for r in known:
            if r["npc_name"] and r["npc_name"].lower() in ans_low:
                return r["npc_name"], r
        if len(known) == 1:
            return known[0]["npc_name"], known[0]
        return None

    async def _find_same_npc(
        self, character_id: str, npc_name: str | None, appearance: str
    ) -> tuple[str, object] | None:
        """Найти среди известных NPC персонажа того же, что описан в теге.

        Модель при повторном осмотре даёт ДРУГОЕ имя NPC («торговец тканями»
        вместо «Тео») или обобщение («тот же охотник»). Точное совпадение по
        имени не срабатывает — спрашиваем LLM с полным контекстом известных
        NPC: это тот же NPC или новый? Возвращает (имя_из_БД, row) или None.

        Пайплайн: загрузка → фильтр → листинг → LLM → сопоставление.
        """
        rows = await tag_db.get_npc_appearance_rows(character_id)

        # Оставляем только записи с описанием и картинкой (полноценные NPC)
        known = self._load_full_npcs_sync(rows)
        if not known:
            return None

        known_text = self._format_npc_listing(known)
        new_label = f"Имя: {npc_name or '(безымянный)'} | Внешность: {appearance[:400]}"

        answer = await self._ask_llm_same_npc(known_text, new_label)
        return self._match_known_by_answer(known, answer)


    # ── _detect_combat_from_text ──


    async def _extract_npc_tag_from_reply(self, reply: str, npc_name: str) -> str | None:
        """Вытащить [NPC: имя|описание внешности] из ответа модели одним LLM-вызовом."""
        try:
            resp = await self.client.chat.completions.create(
                model=settings.appearance_prompt_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты вытаскиваешь из описания NPC его ВНЕШНОСТЬ. "
                            "Верни ТОЛЬКО тег в формате: [NPC: ИМЯ|краткое описание внешности]. "
                            "Никакого другого текста, только тег."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Имя NPC: {npc_name}\n\nОписание:\n{reply[:2500]}",
                    },
                ],
                max_tokens=200,
                temperature=0,
                extra_body=POLZA_EXTRA_BODY,
            )
            msg = resp.choices[0].message
            out = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
            if out.startswith("[NPC:") and "|" in out:
                return out
            return None
        except Exception:
            logger.exception("NPC tag extraction failed")
            return None


    # ── _generate_appearance_image ──


    async def _get_known_npcs(self, character_id: str) -> str:
        """Список известных игроку NPC (имя + краткое описание) для system-промпта."""
        rows = await tag_db.fetch_rows(
            "SELECT npc_name, appearance FROM npc_appearance "
            "WHERE character_id = ? AND appearance_url IS NOT NULL "
            "ORDER BY updated_at DESC LIMIT 10",
            (character_id,),
        )
        if not rows:
            return ""
        parts = []
        for r in rows:
            name = (r["npc_name"] or "").strip()
            appr = (r["appearance"] or "").strip()
            if not appr:
                continue
            label = f"NPC «{name}»" if name else "безымянный NPC"
            parts.append(f"- {label}: {appr[:220]}")
        return "\n".join(parts)


    # ── _get_npc_state_list ──


    async def _get_npc_state_list(self, character_id: str | None, limit: int = 25) -> str:
        """Список известных игроку NPC с их СОСТОЯНИЕМ для system-промпта.

        В отличие от старого _get_known_npcs (только те, у кого есть картинка),
        этот список берёт ВСЕХ зарегистрированных NPC и показывает их статус:
        жив/мёртв, где, отношение. Модель видит «Агата — МЁРТВА (убита тобой)»
        и не может воскресить её при повторном визите.
        """
        if not character_id:
            return ""
        rows = await tag_db.fetch_rows(
            """SELECT npc_name, role, alive, location, attitude, description
               FROM npcs WHERE character_id = ?
               ORDER BY (alive = 0), last_seen_at DESC LIMIT ?""",
            (character_id, limit),
        )

        if not rows:
            return ""
        parts = []
        for r in rows:
            name = (r["npc_name"] or "").strip()
            if not name:
                continue
            status = "💀 МЁРТВ" if not r["alive"] else "жив"
            loc = (r["location"] or "").strip()
            att = (r["attitude"] or "").strip()
            desc = (r["description"] or "").strip()
            bits = [f"«{name}» — {status}"]
            if loc:
                bits.append(f"в: {loc}")
            if att:
                bits.append(f"отношение: {att}")
            if desc:
                bits.append(f"({desc[:120]})")
            parts.append("- " + ", ".join(bits))
        return "\n".join(parts)


    # ── _get_quests_for_prompt ──


    async def _npc_fallback_match(
        self, user_message: str, reply: str, character_id: str
    ) -> tuple[str | None, str | None]:
        """Если модель не поставила [NPC:], но игрок рассматривает известного NPC:
        - без изменений внешности → сохранённая картинка (кэш-hit);
        - с маркерами изменения → извлекаем описание из reply и генерим заново."""
        # Маркеры «рассматривания» в сообщении игрока
        inspect_markers = (
            "рассматрива", "осматрива", "вглядыва", "изуча", "вплотную",
            "разглядыва", "смотрю на", "смотрю в", "вижу его", "вижу её",
            "тот же", "снова", "опять", "подхожу", "оцениваю",
        )
        if not any(m in user_message.lower() for m in inspect_markers):
            return None, None

        # Маркеры «внешность изменилась» — кэш отдавать нельзя
        change_markers = (
            "изменил", "изменилась", "изменился", "теперь", "шрам", "рана",
            "новая внешность", "стал", "перевязан", "другой", "постарел",
            "покалечен", "изуродован", "побрил", "отрастил", "похудел",
        )
        changed = any(m in user_message.lower() for m in change_markers)

        rows = await tag_db.fetch_rows(
            "SELECT npc_name, appearance_url FROM npc_appearance "
            "WHERE character_id = ? AND appearance_url IS NOT NULL",
            (character_id,),
        )

        reply_low = reply.lower()
        for r in rows:
            name = (r["npc_name"] or "").strip()
            if not name:
                continue
            # Имя NPC упомянуто в ответе модели → это он
            if name.lower() in reply_low:
                if not changed:
                    return r["appearance_url"], name  # кэш-hit
                # Внешность изменилась, но модель не дала тег — извлекаем
                # новое описание из её ответа и прогоняем через обычный путь.
                tag = await self._extract_npc_tag_from_reply(reply, name)
                if tag:
                    _, url2, name2 = await self._process_npc_tags(tag, character_id)
                    if url2:
                        return url2, name2
                return None, None  # не отдаём устаревший кэш при изменении
        return None, None


    # ── _npc_pool_size ──


    async def _npc_pool_size(self, npc_name: str) -> int:
        """Сколько картинок этого NPC уже в пуле (kind='npc', тот же npc_name).

        Делегирует в app.services.image_pool — единая точка доступа к image_assets.
        """
        if not npc_name:
            return 0
        return await image_pool_size("npc", "npc_name", npc_name)


    # ── _pick_pool_npc ──


    async def _pick_pool_npc(self, npc_name: str, user_id: str) -> str | None:
        """Взять из пула NPC картинку, которую этот игрок ещё не видел.

        Делегирует в app.services.image_pool.pick_unviewed_from_pool: unseen →
        ротация по use_count, инкремент use_count и отметка просмотра атомарны
        на одном соединении.
        """
        if not npc_name:
            return None
        return await pick_unviewed_from_pool("npc", "npc_name", npc_name, user_id)


    # ── _process_appearance_tags ──


    async def _process_npc_state_tags(self, reply: str, character_id: str | None, location: str = "") -> str:
        """Реестр NPC со стейтом: [NPC_STATE: имя|статус|локация|отношение].

        Статус: жив/мёртв/убит/ранен/исчез. Отношение: дружелюбно/нейтрально/
        враждебно/боится/влюблён. Регистрирует NPC в таблице npcs, чтобы:
        - убитая бабка НЕ воскресала при повторном визите (промпт видит «мёртв»);
        - одинаковые NPC не плодились на разных персонажах (имя уникально
          в рамках character_id);
        - мир помнил отношение NPC к игроку.

        Плюс авторегистрация из [NPC: имя|описание]: если NPC упомянут впервые —
        добавляем строку alive=1 в текущей локации.

        Разбор тегов и SQL-апсерты вынесены в app.services.tag_db; здесь только
        итерация по тегам.
        """
        if not character_id:
            return reply

        try:
            # ── [NPC_STATE: имя|статус|локация|отношение] ──
            for m in re.finditer(r"\[NPC_STATE:\s*([^\]]+)\]", reply):
                fields = tag_db.parse_npc_state_parts(m.group(1).strip(), location or "")
                if not fields["name"]:
                    continue
                alive = 0 if fields["status"] in tag_db.NPC_DEAD_STATUSES else 1
                await tag_db.upsert_npc_state(
                    character_id, fields["name"], alive,
                    fields["location"], fields["attitude"],
                )

            # ── Авторегистрация из [NPC: имя|описание] ──
            for m in re.finditer(r"\[NPC:\s*([^\]]+)\]", reply):
                raw = m.group(1).strip()
                name_part = raw.split("|", 1)[0].strip() if "|" in raw else ""
                if not name_part:
                    continue
                desc = raw.split("|", 1)[1].strip() if "|" in raw else raw
                await tag_db.upsert_npc_authorregistered(
                    character_id, name_part, desc, location or ""
                )
        except Exception:
            logger.exception("NPC state tag processing failed")
        return reply


    # ── _process_npc_tags ──

    async def _resolve_npc_row(self, db, character_id: str, npc_name: str | None, appearance: str):
        """Найти существующую запись NPC: по имени, затем по смыслу (LLM-сравнение).

        Returns (matched_name, row | None).
        """
        row = None
        matched_name = npc_name
        # Безымянных ищем только по семантике (по имени SELECT не сработает)
        if npc_name:
            cur = await db.execute(
                "SELECT rowid AS _rowid, appearance, appearance_url FROM npc_appearance WHERE character_id = ? AND npc_name = ?",
                (character_id, npc_name),
            )
            row = await cur.fetchone()
        # Точного совпадения по имени нет — пытаемся найти того же NPC по смыслу
        # среди известных персонажу NPC. Модель при повторном осмотре может дать
        # ДРУГОЕ имя («торговец тканями» вместо «Тео») — но это тот же NPC.
        if not row:
            matched = await self._find_same_npc(character_id, npc_name, appearance)
            if matched:
                matched_name, row = matched
        return matched_name, row

    async def _upsert_npc_appearance(self, db, character_id: str, npc_name: str | None,
                                     appearance: str, url: str | None, row) -> None:
        """Сохранить внешность NPC (и картинку, если есть): UPDATE по rowid или INSERT ON CONFLICT."""
        if row is not None:
            if url:
                await db.execute(
                    "UPDATE npc_appearance SET npc_name = ?, appearance = ?, appearance_url = ?, updated_at = datetime('now') WHERE rowid = ?",
                    (npc_name, appearance, url, row["_rowid"]),
                )
            else:
                await db.execute(
                    "UPDATE npc_appearance SET npc_name = ?, appearance = ?, updated_at = datetime('now') WHERE rowid = ?",
                    (npc_name, appearance, row["_rowid"]),
                )
        elif url:
            await db.execute(
                """
                INSERT INTO npc_appearance (character_id, npc_name, appearance, appearance_url, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(character_id, npc_name)
                DO UPDATE SET appearance = excluded.appearance, appearance_url = excluded.appearance_url,
                              updated_at = datetime('now')
                """,
                (character_id, npc_name, appearance, url),
            )
        else:
            await db.execute(
                """
                INSERT INTO npc_appearance (character_id, npc_name, appearance, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(character_id, npc_name)
                DO UPDATE SET appearance = excluded.appearance, updated_at = datetime('now')
                """,
                (character_id, npc_name, appearance),
            )

    async def _try_npc_pool(self, db, character_id: str, npc_name: str | None, appearance: str,
                            matched_name: str | None, row, user_id: str) -> str | None:
        """Пул NPC накопил достаточно вариантов (≥NPC_POOL_MIN) → берём из пула, не генерим.

        Индивидуальность: игрок не должен видеть картинку того же NPC, которую уже
        видел (в т.ч. старым персонажем после пересоздания).
        Возвращает URL из пула или None.
        """
        if not npc_name:
            return None
        pool = await self._npc_pool_size(npc_name)
        if pool < NPC_POOL_MIN:
            return None
        pool_url = await self._pick_pool_npc(npc_name, user_id)
        if not pool_url:
            return None
        logger.info("🖼️ NPC reused from pool (name=%s, pool=%d): %s", npc_name, pool, pool_url)
        # Привязываем выбранную картинку к NPC для этого персонажа
        await self._upsert_npc_appearance(db, character_id, matched_name, appearance, pool_url, row)
        await db.commit()
        return pool_url

    async def _generate_and_store_npc(self, db, clean: str, character_id: str, npc_name: str | None,
                                      appearance: str, matched_name: str | None, row, old_appearance: str):
        """Сгенерить новую картинку NPC и сохранить (даже без картинки — помним внешность)."""
        # Генерим: старая внешность + изменения (если были)
        prompt = await self._build_npc_prompt_en(
            npc_name=npc_name, appearance=appearance, old_appearance=old_appearance or None
        )
        url = await self._generate_appearance_image(prompt)
        if not url:
            logger.warning("NPC image: both providers failed name=%s", npc_name)
            await self._upsert_npc_appearance(db, character_id, matched_name, appearance, None, row)
            await db.commit()
            return clean, None, npc_name

        await self._upsert_npc_appearance(db, character_id, matched_name, appearance, url, row)
        await db.commit()
        logger.info("🖼️ NPC image updated name=%s url=%s", matched_name, url)
        # Свежая картинка NPC в общий пул (kind='npc', по имени) — наполняем базу
        if matched_name:
            await self._save_npc_entry(
                url=url, npc_name=matched_name, character_id=character_id,
                meta={"appearance": appearance},
                tags=[t for t in (matched_name, appearance) if t],
            )
        return clean, url, npc_name

    async def _process_npc_tags_with_db(self, db, clean: str, character_id: str,
                                        npc_name: str | None, appearance: str, user_id: str):
        """Основной сценарий _process_npc_tags при наличии character_id."""
        matched_name, row = await self._resolve_npc_row(db, character_id, npc_name, appearance)
        old_appearance = (row["appearance"] if row else "") or ""
        old_url = (row["appearance_url"] if row else "") or ""

        # Описание не изменилось — отдаём сохранённую картинку, не жжём генерации
        if old_url and old_appearance:
            same = await self._appearance_semantically_same(old_appearance, appearance)
            if same:
                return clean, old_url, npc_name

        pool_url = await self._try_npc_pool(db, character_id, npc_name, appearance, matched_name, row, user_id)
        if pool_url:
            return clean, pool_url, npc_name

        return await self._generate_and_store_npc(db, clean, character_id, npc_name, appearance, matched_name, row, old_appearance)

    async def _process_npc_tags(self, reply: str, character_id: str | None, user_id: str = "") -> tuple[str, str | None, str | None]:
        """Вытащить [NPC: имя|описание] тег, сгенерить/обновить картинку NPC.

        Картинка привязана к NPC (по имени) так же, как внешность к персонажу:
        - повторный осмотр того же NPC без изменений → сохранённая картинка;
        - изменения внешности → новая генерация с учётом старого описания.

        Возвращает (clean_reply, npc_url, npc_name):
        - clean_reply — ответ без тега;
        - npc_url — URL картинки NPC (или None);
        - npc_name — имя NPC из тега (или None, если безымянный).
        """
        m = re.search(r'\[NPC:\s*((?:[^\[\]\n]|\[[^\]\n]*\])*)\]', reply)
        if not m:
            return reply, None, None
        clean = re.sub(r'\n?\[NPC:[^\]\n]*\]\n?', '', reply).strip()

        npc_name, appearance = _parse_npc_tag_payload(m.group(1).strip())
        if not appearance:
            return clean, None, npc_name

        # Нет персонажа — генерим без привязки к сущности
        if not character_id:
            return clean, await self._generate_anon_npc_image(npc_name, appearance), npc_name

        db = await get_db()
        try:
            return await self._process_npc_tags_with_db(db, clean, character_id, npc_name, appearance, user_id)
        except Exception:
            logger.exception("NPC tag processing failed")
            return clean, None, npc_name
        finally:
            await db.close()


    # ── _process_quest_tags ──


    async def _save_npc_entry(self, url: str, npc_name: str = "", character_id: str = "",
                              meta: dict | None = None, tags: list | None = None) -> None:
        """Делегирует в image_pool.save_npc_entry — общий пул image_assets."""
        await save_npc_entry(url, npc_name=npc_name, character_id=character_id,
                             meta=meta, tags=tags)


    # ── _weather_and_time ──


