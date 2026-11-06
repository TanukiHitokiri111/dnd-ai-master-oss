"""Модели заклинаний и черт (mid-game)."""

from pydantic import BaseModel, Field, model_validator


class SpellCreate(BaseModel):
    spell_key: str = Field("", description="Ключ заклинания из SRD (пусто для кастомных)")
    # Поля для кастомного заклинания (если spell_key пуст)
    spell_name: str = Field("", description="Название (обязательно для кастомных)")
    spell_level: int = Field(0, ge=0, le=9, description="Уровень 0-9 (0=заговор)")
    school: str = Field("", description="Школа магии")
    desc: str = Field("", description="Полное описание заклинания")
    casting_time: str = Field("", description="Время накладывания")
    spell_range: str = Field("", description="Дистанция")
    components: str = Field("", description="Компоненты (В/С/М)")
    duration: str = Field("", description="Длительность")
    source: str = Field("", description="Источник: свиток, наставник, диалог с DM...")
    notes: str = Field("")

    @model_validator(mode="after")
    def spell_key_or_name(self):
        """Либо spell_key из SRD, либо spell_name для кастомного заклинания."""
        if not self.spell_key and not self.spell_name:
            raise ValueError("Укажите spell_key (из SRD) или spell_name (для кастомного заклинания)")
        return self


class SpellResponse(BaseModel):
    id: int
    character_id: str
    spell_key: str
    spell_name: str
    spell_level: int
    school: str = ""
    desc: str = ""
    casting_time: str = ""
    range: str = ""
    components: str = ""
    duration: str = ""
    flavor: str = ""
    source: str = ""
    notes: str = ""


class FeatureCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    desc: str = Field("", max_length=2000)
    source: str = Field("", description="Откуда получено")
