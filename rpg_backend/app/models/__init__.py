"""Пакет Pydantic-моделей.

Все модели реэкспортируются отсюда — импорты вида
`from app.models import ChatRequest` продолжают работать.
"""

from app.models.auth import (
    AccessCodeGenerateRequest,
    AuthRequest,
    AuthResponse,
    AuthStatusResponse,
    BoostyLinkRequest,
    LinkBoostyResponse,
    RedeemCodeRequest,
    RedeemCodeResponse,
)
from app.models.payments import (
    GenerateCodesResponse,
    GuestCodeResponse,
    GuestPurchaseRequest,
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentStatusResponse,
    PaymentWebhookResponse,
)
from app.models.chat import ChatRequest, ChatResponse, DiceRoll
from app.models.items import (
    ItemCreate,
    ItemEquip,
    ItemResponse,
    LootRequest,
    LootResponse,
)
from app.models.character import (
    CharacterBackstory,
    CharacterCreate,
    CharacterCreationResult,
    CharacterListResponse,
    CharacterResponse,
    CharacterStats,
    CharacterUpdate,
)
from app.models.srd import (
    SrdBackgroundsResponse,
    SrdClassesResponse,
    SrdEquipmentResponse,
    SrdRacesResponse,
    SrdSpellsResponse,
)
from app.models.spells import FeatureCreate, SpellCreate, SpellResponse
from app.models.health import HealthResponse
from app.models.heritage import MixedHeritageRequest, MixedHeritageResult
from app.models.levelup import CharacterClassInfo, LevelUpRequest, LevelUpResult

__all__ = [
    # auth
    "AccessCodeGenerateRequest",
    "AuthRequest",
    "AuthResponse",
    "AuthStatusResponse",
    "BoostyLinkRequest",
    "LinkBoostyResponse",
    "RedeemCodeRequest",
    "RedeemCodeResponse",
    # payments
    "GenerateCodesResponse",
    "GuestCodeResponse",
    "GuestPurchaseRequest",
    "PaymentCreateRequest",
    "PaymentCreateResponse",
    "PaymentStatusResponse",
    "PaymentWebhookResponse",
    # chat
    "ChatRequest",
    "ChatResponse",
    "DiceRoll",
    # items
    "ItemCreate",
    "ItemEquip",
    "ItemResponse",
    "LootRequest",
    "LootResponse",
    # character
    "CharacterBackstory",
    "CharacterCreate",
    "CharacterCreationResult",
    "CharacterListResponse",
    "CharacterResponse",
    "CharacterStats",
    "CharacterUpdate",
    # srd
    "SrdBackgroundsResponse",
    "SrdClassesResponse",
    "SrdEquipmentResponse",
    "SrdRacesResponse",
    "SrdSpellsResponse",
    # spells
    "FeatureCreate",
    "SpellCreate",
    "SpellResponse",
    # health
    "HealthResponse",
    # heritage
    "MixedHeritageRequest",
    "MixedHeritageResult",
    # levelup
    "CharacterClassInfo",
    "LevelUpRequest",
    "LevelUpResult",
]
