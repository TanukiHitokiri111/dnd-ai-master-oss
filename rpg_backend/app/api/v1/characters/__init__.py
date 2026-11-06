"""Character API v2 — пакет по доменам.

Разбит на модули: srd, heritage, creation, crud, inventory, status, loot,
levelup, world. Все роутеры собираются в единый `router` — импорт
`from app.api.v1.characters import router` продолжает работать.
"""

from fastapi import APIRouter

from app.api.v1.characters.srd import router as srd_router
from app.api.v1.characters.heritage import router as heritage_router
from app.api.v1.characters.creation import router as creation_router
from app.api.v1.characters.crud import router as crud_router
from app.api.v1.characters.inventory import router as inventory_router
from app.api.v1.characters.status import router as status_router
from app.api.v1.characters.loot import router as loot_router
from app.api.v1.characters.levelup import router as levelup_router
from app.api.v1.characters.world import router as world_router

router = APIRouter(tags=["characters"])
router.include_router(srd_router)
router.include_router(heritage_router)
router.include_router(creation_router)
router.include_router(crud_router)
router.include_router(inventory_router)
router.include_router(status_router)
router.include_router(loot_router)
router.include_router(levelup_router)
router.include_router(world_router)

__all__ = ["router"]
