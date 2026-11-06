"""Модели бросков кубиков и чата с AI-мастером."""

from pydantic import BaseModel, Field, field_validator


class DiceRoll(BaseModel):
    dice: list[int] = Field(..., description="Кубики: [6,6,6] для 3d6")
    results: list[int] = Field(..., description="Результаты бросков (клиентские, СЕРВЕР ПЕРЕБРАСЫВАЕТ)")
    modifier: int = Field(0)
    label: str = Field("")
    advantage: bool = Field(False)
    disadvantage: bool = Field(False)


class ChatRequest(BaseModel):
    user_id: str | None = Field(None, max_length=64)  # Берётся из токена, игнорируется
    character_id: str | None = Field(None)
    message: str = Field(..., min_length=1, max_length=4000)
    dice_roll: DiceRoll | None = Field(None)

    @field_validator("message", mode='before')
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be blank")
        return v.strip()


class ChatResponse(BaseModel):
    reply: str
    timestamp: str
    is_dead: bool = False
    gold: int | None = None
    karma: int | None = None
    hp_current: int | None = None
    hp_max: int | None = None
    image_url: str | None = None
    appearance_url: str | None = None
    npc_url: str | None = None
    npc_name: str | None = None
    dice_roll: dict | None = None
    # Уровни и опыт: клиент показывает LevelUpScreen при leveled_up=True
    level: int | None = None
    xp: int | None = None
    xp_gained: int | None = None
    leveled_up: bool = False
