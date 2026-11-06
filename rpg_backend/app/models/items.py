"""Модели инвентаря, экипировки и лута."""

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    item_key: str = Field(..., description="Ключ из ITEM_CATALOG или произвольный")
    item_name: str = Field("", description="Название (авто из каталога если пусто)")
    item_type: str = Field("gear", description="weapon|armor|gear|potion|tool|focus|ammo")
    item_subtype: str = Field("")
    qty: int = Field(1, ge=1)
    slot: str = Field("inventory", description="main_hand|off_hand|two_hands|body|back|inventory")
    equipped: bool = Field(False)
    attunement: bool = Field(False)
    notes: str = Field("")


class ItemResponse(BaseModel):
    id: int
    character_id: str
    item_key: str
    item_name: str
    item_type: str
    item_subtype: str
    qty: int
    slot: str
    equipped: bool
    attunement: bool
    notes: str
    modifiers: dict | None = None
    flavor: str = ""


class ItemEquip(BaseModel):
    slot: str | None = Field(None, description="main_hand|off_hand|two_hands|body|back|inventory — куда экипировать")
    equipped: bool = Field(True)


class LootRequest(BaseModel):
    scene_text: str = Field("", description="Описание сцены (для автоопределения биома)")
    biome: str = Field("", description="Биом вручную: forest|desert|dungeon|mountains|swamp|coast|urban")
    count: int = Field(3, ge=1, le=20, description="Количество предметов")


class LootResponse(BaseModel):
    biome: str
    biome_name: str
    items: list[dict]
