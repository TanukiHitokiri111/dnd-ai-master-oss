import os
import re
import time

import httpx

from app.config import settings, POLZA_EXTRA_BODY
from app.db import get_db
from app.logger import logger
from app.services.tag_processor.base import APPEARANCE_DIR, IMAGE_API_URL, translate_appearance_prompt_en

class AppearanceMixin:
    """Внешность персонажей, генерация изображений."""

    async def _appearance_semantically_same(self, old_appearance: str, appearance: str) -> bool:
        """Семантически сравнить описания внешности: изменилась ли суть?

        Модель при повторном осмотре перефразирует описание — байт-в-байт
        сравнение давало ложное «изменилось» и жгло генерации. Спрашиваем LLM:
        вернуть True (та же картинка), только если внешность НЕ изменилась по сути.
        """
        if old_appearance.strip() == appearance.strip():
            return True
        try:
            resp = await self.client.chat.completions.create(
                model=settings.appearance_prompt_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты сравниваешь два описания внешности одного и того же "
                            "персонажа/NPC из RPG. Ответь СТРОГО в формате JSON, ничего "
                            "кроме JSON: {\"changed\": true} если внешность изменилась по "
                            "сути (новая рана, шрам, одежда, причёска, телосложение, "
                            "отличительные черты появились/исчезли), {\"changed\": false} "
                            "если второе описание просто пересказывает то же самое."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"ОПИСАНИЕ 1: {old_appearance}\n\nОПИСАНИЕ 2: {appearance}",
                    },
                ],
                max_tokens=200,
                temperature=0,
                extra_body=POLZA_EXTRA_BODY,
            )
            msg = resp.choices[0].message
            answer = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
            logger.info("Appearance semantic compare: %r (old_len=%d new_len=%d)", answer, len(old_appearance), len(appearance))
            # Пустой ответ модели — не можем утверждать «та же внешность»; считаем изменённой,
            # чтобы не застрять на устаревшем портрете.
            if not answer:
                logger.warning("Appearance semantic compare: empty response, regenerating")
                return False
            # Ответ может быть в reasoning_content. Ищем JSON {"changed": true/false}.
            import json as _json
            try:
                m = re.search(r'\{[^{}]*"changed"\s*:\s*(true|false)[^{}]*\}', answer, re.IGNORECASE)
                if m:
                    return _json.loads(m.group(0))["changed"] is False
            except Exception:
                pass
            # Фолбэк: ДА/НЕТ первым словом
            up = answer.upper()
            if up.startswith("ДА"):
                return False
            if up.startswith("НЕТ"):
                return True
            # Маркеры изменения по сути (только вне пересказа системного промпта)
            change_markers = (
                "ШРАМ", "РАН", "НОВЫЙ", "ДОБАВИЛ", "ПОЯВИЛ", "ИЗМЕНИЛСЯ",
                "CHANGED", "NEW", "ADD", "DIFFERENT", "SCAR", "WOUND", "INJUR",
            )
            if any(m in up for m in change_markers):
                return False  # внешность изменилась → генерим новую
            return True  # маркеров нет → считаем той же внешностью
        except Exception:
            # При ошибке сравнения — считаем, что внешность изменилась (генерим заново)
            logger.exception("Appearance semantic compare failed, regenerating")
            return False


    # ── _appearance_via_image_api ──


    async def _appearance_via_image_api(self, prompt: str) -> str | None:
        """Портрет через внешний OpenAI-совместимый image-шлюз."""
        if not IMAGE_API_URL:
            return None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=10.0)) as client:
                resp = await client.post(
                    f"{IMAGE_API_URL}/v1/chat/completions",
                    json={
                        "model": "freeforai-image",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                m = re.search(r'!\[[^\]]*\]\((/generated/[^)]+)\)', content)
                if not m:
                    logger.warning("Appearance image: no markdown image in router reply: %.120s", content)
                    return None
                gen_path = m.group(1)
                # Безопасность: путь от внешнего API, только /generated/
                if not gen_path.startswith("/generated/"):
                    logger.warning("Appearance image: invalid gen_path from router: %s", gen_path)
                    return None
                img_resp = await client.get(f"{IMAGE_API_URL}{gen_path}")
                img_resp.raise_for_status()
                fname = gen_path.rsplit("/", 1)[-1]
                # Санитайз: путь приходит от внешнего API, не допускаем path traversal
                fname = re.sub(r"[^A-Za-z0-9._-]", "_", fname)
                if ".." in fname or fname.startswith("."):
                    fname = f"appearance_{int(time.time() * 1000)}.png"
                if not fname.endswith(".png"):
                    fname += ".png"
                APPEARANCE_DIR.mkdir(parents=True, exist_ok=True)
                (APPEARANCE_DIR / fname).write_bytes(img_resp.content)
                return f"/api/v1/chat/appearance/{fname}"
        except Exception as e:
            logger.warning("Appearance image via image api failed: %s", e)
            return None


    # ── _appearance_via_alt_api ──


    async def _appearance_via_alt_api(self, prompt: str) -> str | None:
        """Запасной путь: OpenAI-совместимый /images/generations с b64_json."""
        alt_url = settings.image_api_alt_url
        api_key = settings.image_api_alt_key
        if not alt_url or not api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=10.0)) as client:
                resp = await client.post(
                    alt_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.image_api_alt_model,
                        "prompt": prompt,
                        "n": 1,
                        "size": "1024x1024",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                b64 = (data.get("data") or [{}])[0].get("b64_json", "")
                if not b64:
                    logger.warning("Appearance alt image api: no b64_json in response")
                    return None
                fname = f"appearance_{int(time.time() * 1000)}.png"
                APPEARANCE_DIR.mkdir(parents=True, exist_ok=True)
                import base64 as _b64
                (APPEARANCE_DIR / fname).write_bytes(_b64.b64decode(b64))
                return f"/api/v1/chat/appearance/{fname}"
        except Exception as e:
            logger.warning("Appearance image via alt api failed: %s", e)
            return None


    # ── _build_appearance_prompt_en ──


    async def _build_appearance_prompt_en(
        self, race: str, class_name: str, appearance: str, old_appearance: str
    ) -> str:
        """Перевести описание внешности в детальный англ. промпт для image-модели.

        flux-dev (FreeForAI) заметно лучше понимает английский и структурированные
        промпты; русская простыня из 800+ символов превращается у него в
        «случайного орка». Fallback — исходный русский промпт.
        """
        ru = f"Раса: {race}, класс: {class_name}." if (race or class_name) else ""
        if old_appearance:
            ru += f" Раньше: {old_appearance}. Теперь: {appearance}."
        else:
            ru += f" Внешность: {appearance}."

        system_prompt = (
            "You convert Russian D&D character appearance descriptions into "
            "detailed English image-generation prompts. Output ONLY the English "
            "prompt, no preamble, no quotes. Structure: "
            "'Fantasy portrait of {race} {class}, {key physical traits: skin, "
            "eyes, hair, build, face, scars/tattoos, distinctive marks}, wearing "
            "{clothing}. Style: photorealistic, realistic, "
            "cinematic lighting, detailed face, lifelike skin texture, "
            "waist-up, looking at a mirror reflection. "
            "No watermark, no text, no artist signature.'"
        )
        return await translate_appearance_prompt_en(
            self.client, ru,
            system_prompt=system_prompt,
            context_label="Appearance",
        )


    # ── _build_npc_prompt_en ──


    async def _generate_appearance_image(self, prompt: str) -> str | None:
        """Сгенерировать портрет персонажа: основной image-шлюз → запасной."""
        # ── Попытка 1: основной шлюз ──
        url = await self._appearance_via_image_api(prompt)
        if url:
            return url
        # ── Попытка 2: запасной шлюз (если настроен) ──
        url = await self._appearance_via_alt_api(prompt)
        if url:
            return url
        return None


    # ── _get_companions_for_prompt ──


    async def _process_appearance_tags(self, reply: str, character_id: str | None) -> tuple[str, str | None]:
        """Вытащить [APPEARANCE: ...] тег, сгенерить/обновить портрет персонажа.

        Возвращает (clean_reply, appearance_url):
        - clean_reply — ответ без тега;
        - appearance_url — URL нового портрета (или сохранённого, если описание не изменилось).
        """
        import re as _re

        clean = reply
        m = _re.search(r'\[APPEARANCE:\s*((?:[^\[\]\n]|\[[^\]\n]*\])*)\]', reply)
        if not m:
            return reply, None
        appearance = m.group(1).strip()
        clean = _re.sub(r'\n?\[APPEARANCE:[^\]\n]*\]\n?', '', clean).strip()

        if not character_id or not appearance:
            return clean, None

        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT appearance, appearance_url, race, class_name FROM characters WHERE id = ?",
                (character_id,),
            )
            row = await cur.fetchone()
            if not row:
                return clean, None
            old_appearance = row["appearance"] or ""
            old_url = row["appearance_url"] or ""
            race = row["race"] or ""
            class_name = row["class_name"] or ""

            # Описание не изменилось — отдаём сохранённый портрет, не жжём генерации
            if old_url and old_appearance:
                same = await self._appearance_semantically_same(old_appearance, appearance)
                if same:
                    return clean, old_url

            # Генерим портрет: старая внешность + изменения (если были).
            # (русская заготовка ниже перезаписывается англ. промптом из
            # _build_appearance_prompt_en — исторический артефакт, оставлен
            # как документация желаемого описания)
            base = f"Раса: {race}, класс: {class_name}. " if (race or class_name) else ""
            if old_appearance:
                prompt = (
                    f"Нарисуй портрет персонажа D&D. {base}"
                    f"Раньше он выглядел так: {old_appearance}. "
                    f"Теперь он выглядит так: {appearance}. "
                    "Сохрани общие черты лица и телосложения, добавь указанные изменения."
                )
            else:
                prompt = f"Нарисуй портрет персонажа D&D. {base}Внешность: {appearance}"

            # Переводим в детальный англ. промпт для image-модели (flux-dev понимает англ. лучше)
            prompt = await self._build_appearance_prompt_en(
                race=race, class_name=class_name, appearance=appearance, old_appearance=old_appearance
            )

            url = await self._generate_appearance_image(prompt)
            if not url:
                logger.warning("Appearance image: both providers failed, char=%s", character_id[:12])
                # Сохраняем описание даже без картинки — чтобы мастер помнил внешность
                await db.execute(
                    "UPDATE characters SET appearance = ?, updated_at = datetime('now') WHERE id = ?",
                    (appearance, character_id),
                )
                await db.commit()
                return clean, None

            await db.execute(
                "UPDATE characters SET appearance = ?, appearance_url = ?, updated_at = datetime('now') WHERE id = ?",
                (appearance, url, character_id),
            )
            await db.commit()
            logger.info("🖼️ appearance updated char=%s url=%s", character_id[:12], url)
            # Портрет в общий пул (kind='character') — переиспользуется для похожих героев
            await self._save_npc_entry(
                url=url, npc_name="", character_id=character_id,
                meta={"race": race, "class_name": class_name, "appearance": appearance},
                tags=[t for t in (race, class_name, appearance) if t],
            )
            return clean, url
        except Exception:
            logger.exception("Appearance tag processing failed")
            return clean, None
        finally:
            await db.close()


    # ── _process_break_tags ──


