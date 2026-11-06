"""Пакет обработки тегов DM.

Разбит на доменные миксины; TagProcessorMixin собирает их все.
Импорты `from app.services.tag_processor import TagProcessorMixin, _TAG_RE`
и модульные функции process_gold_tags/process_hp_tags/process_shop_tags
продолжают работать.
"""

from app.services.tag_processor.base import (
    _TAG_RE,
    IMAGE_API_URL,
    APPEARANCE_DIR,
    NPC_POOL_MIN,
    process_gold_tags,
    process_hp_tags,
    process_shop_tags,
)
from app.services.tag_processor.appearance import AppearanceMixin
from app.services.tag_processor.npc import NpcMixin
from app.services.tag_processor.combat import CombatMixin
from app.services.tag_processor.progression import ProgressionMixin
from app.services.tag_processor.items import ItemsMixin
from app.services.tag_processor.companions import CompanionsMixin
from app.services.tag_processor.travel import TravelMixin


class TagProcessorMixin(
    AppearanceMixin,
    NpcMixin,
    CombatMixin,
    ProgressionMixin,
    ItemsMixin,
    CompanionsMixin,
    TravelMixin,
):
    """Объединённый миксин обработки тегов DM."""

    pass


__all__ = [
    "TagProcessorMixin",
    "_TAG_RE",
    "IMAGE_API_URL",
    "APPEARANCE_DIR",
    "NPC_POOL_MIN",
    "process_gold_tags",
    "process_hp_tags",
    "process_shop_tags",
]
