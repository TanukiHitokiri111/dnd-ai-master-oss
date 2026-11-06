"""Модели персонажа: создание, обновление, ответы."""

from pydantic import BaseModel, Field
from typing import Any

from app.models.items import ItemResponse


class CharacterCreate(BaseModel):
    """Шаг 1: раса + класс + имя + подкласс + подраса (опционально)."""
    name: str = Field(..., min_length=1, max_length=64)
    # 64: длинные фракционные названия миров (дальний космос: «Орден
    # Варп-Навигаторов Фиолетового Тумана» = 41 символ) не влезают в 32
    race: str = Field(..., min_length=1, max_length=64)
    class_name: str = Field(..., min_length=1, max_length=32)
    background_name: str = Field("", max_length=32)
    subclass: str = Field("", max_length=64)
    subrace: str = Field("", max_length=64, description="Ключ подрасы (напр. 'black' для Драконорождённого)")
    mixed_heritage: dict | None = Field(None, description="Результат roll_mixed_heritage если раса 'Смешанная'")
    stats: dict[str, int] | None = Field(None, description="Характеристики (если не указаны — стандартный набор)")
    alignment: str = Field("", max_length=32, description="Мировоззрение")
    background: str = Field("", max_length=32, description="Предыстория (синоним background_name)")
    world: str = Field("forgotten_realms", max_length=64, description="Начальный мир (ключ из WORLD_TEMPLATES)")


class CharacterStats(BaseModel):
    """Шаг 2: характеристики."""
    stats: dict[str, int] = Field(
        default_factory=lambda: {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    )
    skill_proficiencies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class CharacterBackstory(BaseModel):
    """Шаг 3: предыстория."""
    backstory: str = Field("", max_length=2000, description="Предыстория от лица персонажа")


class CharacterCreationResult(BaseModel):
    """Результат создания персонажа."""
    character: dict[str, Any]
    dm_notes: str = Field("", description="Заметки мастера (если AI что-то изменил)")
    starting_items: list[dict[str, Any]] = Field(default_factory=list)
    features: list[dict[str, Any]] = Field(default_factory=list)
    racial_traits: list[dict[str, Any]] = Field(default_factory=list)
    subclass: str = Field("", description="Ключ выбранного подкласса")
    subclass_features: list[dict[str, Any]] = Field(default_factory=list)


class CharacterUpdate(BaseModel):
    """Обновление полей персонажа. level исключён — менять через level-up."""
    name: str | None = None
    xp: int | None = Field(None, ge=0)
    hp_current: int | None = Field(None, ge=0)
    hp_max: int | None = Field(None, ge=1)
    ac: int | None = Field(None, ge=0)
    init_ac: int | None = Field(None, ge=0)
    speed: int | None = Field(None, ge=1)
    stats: dict[str, int] | None = None
    backstory: str | None = None
    features: list[dict[str, Any]] | None = None
    proficiencies: dict[str, Any] | None = None
    skill_proficiencies: list[str] | None = None
    languages: list[str] | None = None
    background_name: str | None = None
    subclass: str | None = None


class CharacterResponse(BaseModel):
    """Полный ответ о персонаже со всем инвентарём."""
    id: str
    user_id: str
    name: str
    race: str
    class_name: str
    background_name: str
    level: int
    xp: int = 0
    stats: dict[str, int]
    hp_max: int
    hp_current: int
    ac: int
    init_ac: int
    speed: int
    backstory: str
    features: list[dict[str, Any]]
    proficiencies: dict[str, Any]
    skill_proficiencies: list[str]
    languages: list[str]
    items: list[ItemResponse]
    created_at: str
    updated_at: str


class CharacterListResponse(BaseModel):
    """Список персонажей."""
    characters: list[dict[str, Any]]
