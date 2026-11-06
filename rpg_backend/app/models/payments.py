"""Модели платежей (YooKassa) и гостевых покупок."""

from pydantic import BaseModel, Field, field_validator


class PaymentCreateRequest(BaseModel):
    days: int = Field(..., ge=1, le=365, description="Количество дней")


class PaymentCreateResponse(BaseModel):
    ok: bool
    payment_id: str = ""
    confirmation_url: str = ""
    amount_rub: int = 0
    error: str = ""


class PaymentWebhookResponse(BaseModel):
    ok: bool
    user_id: str = ""
    days_added: int = 0
    new_expires: str = ""
    activation_code: str = ""  # для guest-покупок — код активации


class PaymentStatusResponse(BaseModel):
    tier: str
    expires_at: str
    days_left: int


class GuestPurchaseRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, description="D&D username")

    @field_validator("username")
    @classmethod
    def alphanumeric(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_\-]+$', v):
            raise ValueError("Только буквы, цифры, _ и -")
        return v.strip()


class GuestCodeResponse(BaseModel):
    status: str = "pending"  # pending | activated | activate_after_register | not_found


class GenerateCodesResponse(BaseModel):
    codes: list[str]
