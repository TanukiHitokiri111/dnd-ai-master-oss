"""Броски кубиков на сервере."""

import json
import secrets


def _clamp_dice_modifier(modifier: int, character: dict | None) -> int:
    """Ограничить модификатор разумными пределами по статам персонажа.

    Нельзя вписать +15 к запрошенному DM «d20 + 0»: потолок = максимальный
    стат-модификатор персонажа + бонус мастерства + 5 (запас на магию/баффы).
    Без персонажа — консервативный ±20.
    """
    if not character:
        return max(-20, min(20, modifier))
    stats = character.get("stats") or {}
    if isinstance(stats, str):
        try:
            stats = json.loads(stats)
        except (json.JSONDecodeError, TypeError):
            stats = {}
    try:
        stat_mods = [((int(v) - 10) // 2) for v in stats.values() if isinstance(v, (int, float)) or str(v).lstrip("-").isdigit()]
    except Exception:
        stat_mods = []
    best = max(stat_mods) if stat_mods else 2
    level = int(character.get("level") or 1)
    prof = 2 + (level - 1) // 4  # 2,2,3,3,4,4,5,5,6...
    cap = best + prof + 5
    return max(-cap, min(cap, modifier))


def _server_roll(dice: list[int], modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> dict:
    """Криптостойкий бросок на сервере. Клиент не генерирует результаты.

    advantage/disadvantage: бросаем 2d20, берём max/min (как D&D 5e).
    """
    # Валидация: dice не больше d100
    if any(d > 100 or d < 1 for d in dice):
        raise ValueError("Invalid die size (max d100)")
    if advantage or disadvantage:
        r1 = 1 + secrets.randbelow(20)
        r2 = 1 + secrets.randbelow(20)
        taken = max(r1, r2) if advantage else min(r1, r2)
        results = [taken]
        total = taken + modifier
        return {
            "dice": dice,
            "results": results,
            "modifier": modifier,
            "total": total,
            "server_rolled": True,
            "advantage": advantage,
            "disadvantage": disadvantage,
            "second_result": r2 if advantage else r1,
        }
    results = [1 + secrets.randbelow(d) for d in dice]
    total = sum(results) + modifier
    return {
        "dice": dice,
        "results": results,
        "modifier": modifier,
        "total": total,
        "server_rolled": True,
    }
