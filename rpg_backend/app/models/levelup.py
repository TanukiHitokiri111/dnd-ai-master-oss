"""Модели мультиклассирования и повышения уровня."""

from pydantic import BaseModel, Field, field_validator


class LevelUpRequest(BaseModel):
    """Запрос на повышение уровня."""
    new_class: str | None = Field(None, description="Класс для мультикласса (None = текущий класс)")
    hp_roll: int | None = Field(None, description="Бросок хит-дайса (если None — взять среднее)")
    stat_increase: dict[str, int] | None = Field(None, description="+2/+1 к характеристикам (ровно 2 очка, макс 20 до бонуса)")
    feat_choice: str | None = Field(None, description="Выбранная черта (если уровень даёт черту)")
    spell_choices: list[str] | None = Field(None, description="Выбранные заклинания при повышении уровня заклинателя")
    skill_choices: list[str] | None = Field(None, description="Выбранные навыки (если мультикласс даёт навыки)")

    @field_validator("stat_increase")
    @classmethod
    def max_two_points(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        total = sum(v.values())
        if total != 2:
            raise ValueError(f"Сумма повышений статов должна быть ровно 2, получено {total}")
        return v


class CharacterClassInfo(BaseModel):
    """Информация об одном классе персонажа (для мультикласса)."""
    class_name: str
    level: int
    hit_die: int
    subclass: str = ""


class LevelUpResult(BaseModel):
    """Результат повышения уровня."""
    character_id: str
    total_level: int
    classes: list[CharacterClassInfo]
    hp_gained: int
    hp_max_new: int
    features_gained: list[dict[str, str]]
    proficiencies_gained: dict[str, list[str]]
    spell_slots: dict[str, int] | None = None
    stat_increases_applied: dict[str, int] | None = None
    available_spells: list[dict] | None = None
    more_levels: bool = False  # XP хватает ещё на уровень — клиент сразу открывает экран повторно
