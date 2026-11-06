"""Модели смешанного наследия (Смешанные расы)."""

from pydantic import BaseModel, Field, field_validator


class MixedHeritageRequest(BaseModel):
    """Запрос на бросок смешанного наследия."""
    species_percentages: dict[str, int] = Field(
        ..., description='{"Эльф": 50, "Человек": 50} — ключи как в MIXED_HERITAGE_CONFIG'
    )
    seed: int | None = Field(None, description="Зерно для воспроизводимости")

    @field_validator("species_percentages")
    @classmethod
    def at_least_two(cls, v: dict) -> dict:
        if len(v) < 2:
            raise ValueError("Нужно минимум две расы для смешанного наследия")
        return v


class MixedHeritageResult(BaseModel):
    """Результат броска смешанного наследия."""
    dominant_species: str
    species_percentages: dict[str, int]
    physical_traits: list[dict[str, str]]
    magical_traits: list[dict[str, str]]
    visual_traits: list[dict[str, str]]
    speed: int
    size_category: str
    languages: list[str]
    hp_bonus: int
