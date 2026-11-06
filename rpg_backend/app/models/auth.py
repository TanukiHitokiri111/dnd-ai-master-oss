"""Модели авторизации и доступа."""

from pydantic import BaseModel, Field, field_validator


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32)
    password: str = Field(..., min_length=4, max_length=128)
    boosty_login: str | None = Field(None, max_length=64)

    @field_validator("username")
    @classmethod
    def alphanumeric(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_\-]+$', v):
            raise ValueError("Только буквы, цифры, _ и -")
        return v.strip()


class BoostyLinkRequest(BaseModel):
    boosty_login: str = Field(..., min_length=2, max_length=64)


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)


class AccessCodeGenerateRequest(BaseModel):
    count: int = Field(1, ge=1, le=100)
    duration_days: int = Field(7, ge=1, le=365)
    prefix: str = "TANUKI"
    note: str = ""


class AuthStatusResponse(BaseModel):
    is_active: bool
    subscription_tier: str
    subscription_expires: str
    boosty_login: str | None = None
    days_left: int = 0


class LinkBoostyResponse(BaseModel):
    ok: bool
    old_user_deactivated: bool = False


class RedeemCodeResponse(BaseModel):
    ok: bool
    expires_at: str = ""


class AuthResponse(BaseModel):
    token: str
    user_id: str
