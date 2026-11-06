"""Миксин обработки тегов: константы и модульные функции (золото/HP/магазин).

Магазин вынесен в единый движок process_shop_tags_ex: оба пути — модульный
process_shop_tags (групповой чат) и ItemsMixin._process_shop_tags (личный
чат, лимит инвентаря 100 на покупки с ценой) — используют один и тот же код
без клонов.
"""
import random
import re
import time
from pathlib import Path

from app.config import settings, POLZA_EXTRA_BODY
from app.db import get_db
from app.logger import logger

# ── Константы ──
# Внешний сервис генерации портретов: OpenAI-совместимый шлюз с image-моделью.
# Пусто — портреты не генерируются, игра работает без картинок.
IMAGE_API_URL = settings.image_api_url
APPEARANCE_DIR = Path("/app/data/appearance")
NPC_POOL_MIN = 20

# ── Единый реестр тегов (динамическая генерация вместо 9+ одинаковых regexp) ──
# Каждый тег вида [NAME: ...] описывается одним элементом кортежа; полный
# античит-паттерн _TAG_RE собирается из этого же списка — новый тег добавляется
# одной строкой, без копирования структуры регулярок.
_TAG_KINDS: tuple[str, ...] = (
    "ITEM", "BREAK", "SYSTEM", "DM", "SPELL", "NPC", "APPEARANCE", "GOLD",
    "XP", "STATE", "QUEST", "KARMA", "SHOP", "SELL", "COMPANION",
    "COMPANION_STATE", "HP", "REVIVE", "INIT", "COMBAT_END", "REST", "TRAVEL",
)
_TAGS_PATTERN = "|".join(re.escape(k) for k in _TAG_KINDS)
# Анти-чит паттерн для удаления тегов из сообщений игрока
_TAG_RE = re.compile(rf"\[(?:{_TAGS_PATTERN})\s*:.*?\]", re.I | re.S)
# Парсеры отдельных тегов [TAG: тело] — один компилятор на все виды, ключ = имя тега.
_TAG_BODY_RE = r"\[{}\s*:\s*(.*?)\s*\]"
_TAG_PATTERNS: dict[str, re.Pattern] = {k: re.compile(_TAG_BODY_RE.format(re.escape(k)), re.I | re.S) for k in _TAG_KINDS}
# Специализированные парсеры с ценой («|число») для магазина
_SHOP_SELL_BODY_RE = r"\[{}\s*:\s*([^\]|]+?)\s*(?:\|\s*(\d+))?\s*\]"
_SHOP_ITEM_RE: dict[str, re.Pattern] = {
    kind: re.compile(_SHOP_SELL_BODY_RE.format(kind), re.I | re.S) for kind in ("SHOP", "SELL")
}

# Модульный реестр транзакций золота (античит темпа). Используется process_gold_tags.
_gold_transactions: dict[str, list[tuple[float, int]]] = {}
# Реестр XP транзакций (античит темпа XP)
_xp_transactions: dict[str, list[tuple[float, int]]] = {}


# ── Античит золота ──


def _clamp_gold_delta(character_id: str, delta: int) -> int | None:
    """Античит темпа начислений: макс. +200 золота за 5 минут.

    Возвращает скорректированную дельту или None, если транзакция
    заблокирована полностью (лимит исчерпан). Отрицательные дельты
    проходят без ограничений.
    """
    if delta <= 0:
        return delta
    now = time.time()
    tx_list = _gold_transactions.setdefault(character_id, [])
    cutoff = now - 300
    tx_list[:] = [(t, a) for t, a in tx_list if t >= cutoff]
    total_recent = sum(a for _, a in tx_list)
    if total_recent + delta > 200:
        allowed = 200 - total_recent
        if allowed <= 0:
            logger.warning("💰 ANTICHEAT char=%s rate limit exceeded, blocked +%d", character_id[:12], delta)
            return None
        logger.info("💰 ANTICHEAT char=%s reduced +%d→+%d (rate limit)", character_id[:12], delta, allowed)
        delta = allowed
    tx_list.append((now, delta))
    return delta


# ── process_gold_tags ──


async def _apply_gold_delta(character_id: str, delta: int) -> tuple[str, int | None]:
    """Применить дельту золота к персонажу в БД.

    Возвращает (статус, новое_золото):
    - "ok"           — применено, вернули новый баланс;
    - "insufficient" — недостаточно золота для списания;
    - "no_char"      — персонаж не найден;
    - "error"        — сбой БД (залогирован).
    """
    db = await get_db()
    try:
        cur = await db.execute("SELECT gold FROM characters WHERE id = ?", (character_id,))
        row = await cur.fetchone()
        if not row:
            logger.warning("[GOLD] character %s not found", character_id)
            return "no_char", None
        gold = row["gold"] or 0
        if delta < 0 and gold + delta < 0:
            logger.info("💰 GOLD char=%s tried to deduct %d but only has %d", character_id[:12], -delta, gold)
            return "insufficient", gold
        new_gold = gold + delta
        await db.execute(
            "UPDATE characters SET gold = ?, updated_at = datetime('now') WHERE id = ?",
            (new_gold, character_id),
        )
        await db.commit()
        logger.info("💰 GOLD char=%s %+d, gold=%d", character_id[:12], delta, new_gold)
        return "ok", new_gold
    except Exception:
        logger.exception("Gold transaction failed")
        return "error", None
    finally:
        await db.close()


async def process_gold_tags(reply: str, character_id: str | None) -> tuple[str, int | None]:
    """Обработать [GOLD: +N] / [GOLD: -N] — начисление/списание золота.

    Античит: макс. +200 золота за 5 минут.
    Возвращает (clean_reply, gold_after) — золото после операции (None если тегов нет).
    """
    gold_after = None
    clean = reply

    for m in re.finditer(r'\[GOLD:\s*([+-]?\d+)[^\]]*\]', reply):
        try:
            delta = int(m.group(1))
        except ValueError:
            continue
        if delta == 0:
            continue
        if not character_id:
            clean = clean.replace(m.group(0), "", 1)
            continue

        clamped = _clamp_gold_delta(character_id, delta)
        if clamped is None:
            clean = clean.replace(m.group(0), "⚠️ Слишком много золота за раз (ачивка сокращена)", 1)
            continue

        status, new_gold = await _apply_gold_delta(character_id, clamped)
        if status == "ok" and new_gold is not None:
            gold_after = new_gold
            clean = clean.replace(m.group(0), f"💰 Золото: {new_gold} ЗМ (изменение: {clamped:+d})", 1)
        elif status == "insufficient":
            clean = clean.replace(m.group(0), f"⚠️ Недостаточно золота (есть {new_gold} ЗМ)", 1)
        else:
            # no_char / error — тег оставляем как есть (как раньше)
            pass

    return clean, gold_after


# ── process_hp_tags ──


async def process_hp_tags(reply: str, character_id: str | None) -> tuple[str, int | None, int | None, bool]:
    """Обработать [HP: текущее/макс] — синхронизация HP персонажа с БД.

    Возвращает (clean_reply, hp_current, hp_max, died):
    - clean_reply — ответ без тега;
    - hp_current/hp_max — значения из тега (None если тега нет);
    - died — True если HP упало до 0 (персонаж погиб в этом ответе).
    """
    clean = reply
    m = re.search(r'\[HP:\s*(\d+)\s*/\s*(\d+)\]', reply)
    if not m:
        return reply, None, None, False
    hp_cur, hp_max = int(m.group(1)), int(m.group(2))
    clean = re.sub(r'\n?\[HP:\s*\d+\s*/\s*\d+\]\n?', '', clean).strip()

    died = False
    if character_id:
        db = await get_db()
        try:
            cur = await db.execute("SELECT hp_max, hp_current, is_dead FROM characters WHERE id = ?", (character_id,))
            row = await cur.fetchone()
            if row:
                old_hp = row["hp_current"] or 0
                old_max = row["hp_max"] or hp_max
                hp_max = max(hp_max, old_max)  # не даём модели уменьшить максимум
                hp_cur = min(hp_cur, hp_max)
                # Смерть: HP дошло до 0 (было >0, стало 0)
                if hp_cur <= 0 and old_hp > 0:
                    died = True
                    await db.execute(
                        "UPDATE characters SET hp_current = 0, is_dead = 1, updated_at = datetime('now') WHERE id = ?",
                        (character_id,),
                    )
                    logger.info("💀 DEATH char=%s HP %d→0 — персонаж погиб", character_id[:12], old_hp)
                else:
                    # HP > 0 — персонаж жив. Если был мёртв (is_dead=1) — снимаем смерть
                    if hp_cur > 0:
                        if row["is_dead"]:
                            logger.info("✨ AUTO-REVIVE char=%s HP %d>0 — is_dead снят", character_id[:12], hp_cur)
                        await db.execute(
                            "UPDATE characters SET hp_current = ?, hp_max = ?, is_dead = 0, updated_at = datetime('now') WHERE id = ?",
                            (hp_cur, hp_max, character_id),
                        )
                    else:
                        await db.execute(
                            "UPDATE characters SET hp_current = ?, hp_max = ?, updated_at = datetime('now') WHERE id = ?",
                            (hp_cur, hp_max, character_id),
                        )
                await db.commit()
            else:
                logger.warning("[HP] character %s not found", character_id)
        except Exception:
            logger.exception("HP tag processing failed")
        finally:
            await db.close()

    return clean, hp_cur, hp_max, died


# ── Магазин: общий движок ──


def _get_catalog_price(item_key: str) -> int | None:
    """Рыночная цена из каталога (value_gp), округлённая до целых."""
    from app.knowledge.item_utils import resolve_item
    from app.knowledge.srd_rules import ITEM_CATALOG

    info = resolve_item(item_key)
    cat_key = info["item_key"] if info else item_key
    cat = ITEM_CATALOG.get(cat_key)
    if cat and "value_gp" in cat:
        return int(cat["value_gp"] + 0.5)
    return None


async def _insert_purchased_item(
    db, character_id: str, item_key: str, item_info: dict | None,
) -> None:
    """Вставить купленный предмет в инвентарь (таблица items)."""
    slot = item_info.get("slot", "inventory") if item_info else "inventory"
    flavor = item_info.get("flavor", "Куплено в магазине") if item_info else "Куплено в магазине"
    await db.execute(
        """INSERT INTO items (character_id, item_key, item_name, item_type, item_subtype, qty, slot, equipped, attunement, notes, modifiers, flavor)
           VALUES (?, ?, ?, ?, ?, 1, ?, 0, 0, '', '{}', ?)""",
        (character_id,
         item_info["item_key"] if item_info else item_key,
         item_info["item_name"] if item_info else item_key.replace("_", " ").title(),
         item_info.get("item_type", "gear") if item_info else "gear",
         item_info.get("item_subtype", "") if item_info else "",
         slot, flavor),
    )


async def shop_buy_item(
    character_id: str,
    item_key: str,
    item_info: dict | None,
    price: int,
    *,
    inventory_limit: int | None = None,
    source: str = "",
) -> tuple[str, int | None, int | None]:
    """Покупка предмета: списать золото, положить в инвентарь.

    inventory_limit — проверка переполнения (макс предметов); применяется,
    только если задан (личный чат лимитирует покупки с ценой до 100 позиций).

    Возвращает (статус, gold_after, детали):
    - "bought"       — куплено, gold_after = новый баланс;
    - "insufficient" — не хватает золота (новый баланс в деталях);
    - "capped"       — инвентарь переполнен (текущее кол-во в деталях);
    - "no_char"      — персонаж не найден, тег оставить как есть.
    """
    db = await get_db()
    try:
        cur = await db.execute("SELECT gold FROM characters WHERE id = ?", (character_id,))
        row = await cur.fetchone()
        if not row:
            logger.warning("[SHOP] character %s not found", character_id)
            return "no_char", None, None

        gold = row["gold"] or 0

        if inventory_limit is not None:
            cnt_cur = await db.execute("SELECT COUNT(*) FROM items WHERE character_id = ?", (character_id,))
            cnt_row = await cnt_cur.fetchone()
            if cnt_row and cnt_row[0] >= inventory_limit:
                logger.info("🛒 SHOP char=%s INVENTORY FULL (%d items)%s",
                            character_id[:12], cnt_row[0], f" ({source})" if source else "")
                return "capped", None, cnt_row[0]

        if gold < price:
            logger.info("🛒 SHOP char=%s NOT ENOUGH gold for %s (%d < %d)%s",
                        character_id[:12], item_key, gold, price, f" ({source})" if source else "")
            return "insufficient", None, gold

        gold_after = gold - price
        await db.execute(
            "UPDATE characters SET gold = ?, updated_at = datetime('now') WHERE id = ?",
            (gold_after, character_id),
        )
        await _insert_purchased_item(db, character_id, item_key, item_info)
        await db.commit()
        logger.info("🛒 SHOP char=%s bought %s%s for %d, gold=%d",
                    character_id[:12], item_key, f" ({source})" if source else "", price, gold_after)
        return "bought", gold_after, None
    except Exception:
        logger.exception("Shop purchase failed%s", f" ({source})" if source else "")
        return "error", None, None
    finally:
        await db.close()


async def shop_sell_item(
    character_id: str,
    item_key: str,
    resolved_key: str,
    price: int,
    *,
    source: str = "",
) -> tuple[str, int | None]:
    """Продажа одного экземпляра предмета за золото.

    Возвращает (статус, gold_after):
    - "sold"      — продано, золото начислено;
    - "missing"   — предмета нет в инвентаре;
    - "no_char"   — у персонажа нет строки (удаление выполнено, но начислить некуда;
                    тег оставить как есть);
    - "error"     — сбой БД.
    """
    db = await get_db()
    try:
        cur = await db.execute("SELECT gold FROM characters WHERE id = ?", (character_id,))
        row = await cur.fetchone()
        del_cur = await db.execute(
            """DELETE FROM items WHERE id = (
                   SELECT id FROM items WHERE character_id = ? AND item_key = ? LIMIT 1)""",
            (character_id, resolved_key),
        )
        if del_cur.rowcount == 0:
            logger.info("🛒 SELL char=%s tried to sell %s but not found%s",
                        character_id[:12], item_key, " (auto)" if source == "auto" else "")
            return "missing", None
        if row:
            gold_after = (row["gold"] or 0) + price
            await db.execute(
                "UPDATE characters SET gold = ?, updated_at = datetime('now') WHERE id = ?",
                (gold_after, character_id),
            )
            await db.commit()
            logger.info("🛒 SELL char=%s sold %s%s for %d, gold=%d",
                        character_id[:12], item_key, " (auto-price)" if source == "auto" else "", price, gold_after)
            return "sold", gold_after
        return "no_char", None
    except Exception:
        logger.exception("Shop sell failed%s", " (auto-price)" if source == "auto" else "")
        return "error", None
    finally:
        await db.close()


_SELL_MARKUP_RANGE = (1.5, 3.0)   # множитель цены каталога при покупке (auto)
_SELL_DISCOUNT = 0.4              # доля рыночной цены при продаже скупщику (auto)


async def process_shop_tags_ex(
    reply: str,
    character_id: str | None,
    *,
    priced_inventory_limit: int | None = None,
) -> tuple[str, int | None]:
    """Единый движок магазина: [SHOP]/[SELL] с ценой и автоценой.

    priced_inventory_limit — лимит инвентаря ТОЛЬКО для покупок с явной ценой
    (историческое поведение личного чата: 100 предметов).

    Тег с «|число» — явная цена; без цены — auto:
    [SHOP: ключ] — value_gp × (1.5..3.0); [SELL: ключ] — value_gp × 0.4.
    Операции кумулятивны (каждая перечитывает баланс), порядок обработки
    не влияет на итоговое золото. Возвращает (clean_reply, gold_after).
    """
    from app.knowledge.item_utils import resolve_item

    gold_after = None
    clean = reply

    def _note(new_gold: int | None) -> None:
        nonlocal gold_after
        if new_gold is not None:
            gold_after = new_gold

    def _parse(kind: str) -> list[tuple[str, str, int | None]]:
        """Все теги данного типа: [(полный_тег, ключ, цена|None)]."""
        out = []
        for m in _SHOP_ITEM_RE[kind].finditer(reply):
            item_key = m.group(1).strip()
            try:
                price = int(m.group(2)) if m.group(2) else None
            except ValueError:
                continue
            out.append((m.group(0), item_key, price))
        return out

    def _auto_price(item_key: str, multiplier: float | tuple[float, float]) -> int | None:
        """Auto-цена из каталога: число = фикс. доля, пара = случайный диапазон."""
        catalog_price = _get_catalog_price(item_key)
        if catalog_price is None:
            return None
        if isinstance(multiplier, tuple):
            lo, hi = multiplier
            return int(catalog_price * random.uniform(lo, hi))
        return int(catalog_price * multiplier)

    def _resolved(item_key: str) -> tuple[dict | None, str]:
        """(item_info, отображаемое_имя) — общая логика для SHOP и SELL."""
        info = resolve_item(item_key)
        name = info["item_name"] if info else item_key.replace("_", " ").title()
        return info, name

    def _trade_price(item_key: str, explicit: bool, buy_price: int | None) -> int | None:
        """Цена сделки: явная из тега, иначе auto (наценка для покупки, 40% для продажи)."""
        if buy_price is not None:
            return buy_price
        return _auto_price(item_key, _SELL_MARKUP_RANGE if explicit else _SELL_DISCOUNT)

    async def _sub(tag: str, replacement: str) -> None:
        """Заменить первое вхождение тега в clean."""
        nonlocal clean
        clean = clean.replace(tag, replacement, 1)

    async def _trade(
        tag: str, item_key: str, buy_price: int | None, *, buying: bool,
    ) -> str:
        """Драйвер одной сделки [SHOP]/[SELL] → mutate clean.

        Различия покупки/продажи: статус-ветки и тексты; всё общее
        (resolve, цена, лимит инвентаря, вызов БД, _note) — здесь.
        """
        item_info, item_name = _resolved(item_key)
        explicit = m_group_explicit(tag)
        price = _trade_price(item_key, explicit, buy_price)
        if price is None or not character_id:
            return clean
        if buying:
            limit = priced_inventory_limit if explicit else None
            status, new_gold, detail = await shop_buy_item(
                character_id, item_key, item_info, price,
                inventory_limit=limit,
                source="" if limit is not None else "auto-price",
            )
            _note(new_gold)
            if status == "capped":
                await _sub(tag, f"❌ Инвентарь переполнен ({detail}/{limit})")
            elif status == "bought":
                await _sub(tag, f"🛒 Куплено: {item_name} за {price} зм")
            elif status == "insufficient":
                await _sub(tag, f"❌ Не хватает золота на {item_name} ({price} зм)")
            # no_char/error — тег остаётся как есть
        else:
            resolved_key = item_info["item_key"] if item_info else item_key
            status, new_gold = await shop_sell_item(
                character_id, item_key, resolved_key, price,
                source="auto" if not explicit else "",
            )
            _note(new_gold)
            if status == "missing":
                await _sub(tag, f"⚠️ Нечего продавать: {item_name} нет в инвентаре")
            elif status == "sold":
                await _sub(tag, f"💰 Продано: {item_name} за {price} зм")
        return clean

    # ── Покупка: [SHOP: ключ|цена] и [SHOP: ключ] (auto) ──
    for tag, item_key, price in _parse("SHOP"):
        clean = await _trade(tag, item_key, price, buying=True)

    # ── Продажа: [SELL: ключ|цена] и [SELL: ключ] (auto) ──
    for tag, item_key, price in _parse("SELL"):
        clean = await _trade(tag, item_key, price, buying=False)

    return clean, gold_after


def m_group_explicit(tag: str) -> bool:
    """True если тег содержит явную цену («|число»)."""
    return "|" in tag


async def translate_appearance_prompt_en(
    client,
    ru: str,
    *,
    system_prompt: str,
    context_label: str,
) -> str:
    """Общий переводчик рус. описания внешности в англ. промпт для image-модели.

    Используется AppearanceMixin._build_appearance_prompt_en (персонажи) и
    NpcMixin._build_npc_prompt_en (NPC): один вызов LLM, один фолбэк — разница
    только в system-промпте. Возвращает англ. промпт или исходный ru при сбое.
    """
    try:
        resp = await client.chat.completions.create(
            model=settings.appearance_prompt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ru},
            ],
            max_tokens=600,
            temperature=0.4,
            extra_body=POLZA_EXTRA_BODY,
        )
        msg = resp.choices[0].message
        en = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        if len(en) > 30:
            return en
    except Exception:
        logger.exception("%s prompt translation failed, using RU prompt", context_label)
    return ru


async def ask_llm_text(
    client,
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 200,
    temperature: float = 0,
    context_label: str = "LLM request",
) -> str | None:
    """Один вызов LLM «system+user → текст» — общий низкоуровневый драйвер.

    Используется вспомогательными LLM-вызовами (сравнение внешности, поиск
    того же NPC, извлечение NPC-тега). Возвращает content (или
    reasoning_content при пустом content) либо None при сбое/пустом ответе.
    """
    try:
        resp = await client.chat.completions.create(
            model=model or settings.appearance_prompt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            extra_body=POLZA_EXTRA_BODY,
        )
        msg = resp.choices[0].message
        answer = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        return answer or None
    except Exception:
        logger.exception("%s failed", context_label)
        return None

async def process_shop_tags(reply: str, character_id: str | None) -> tuple[str, int | None]:
    """Обработать [SHOP: ключ|цена] или [SHOP: ключ] — покупка, [SELL: ...] — продажа.

    Модульная точка входа (групповой чат): без лимита инвентаря.
    Личный чат вызывает process_shop_tags_ex с priced_inventory_limit=100.
    Возвращает (clean_reply, gold_after).
    """
    return await process_shop_tags_ex(reply, character_id)