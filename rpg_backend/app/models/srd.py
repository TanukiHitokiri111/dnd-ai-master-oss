"""SRD-справочные модели."""

from pydantic import BaseModel
from typing import Any


class SrdBackgroundsResponse(BaseModel):
    backgrounds: list[dict[str, Any]]


class SrdClassesResponse(BaseModel):
    classes: list[dict[str, Any]]


class SrdRacesResponse(BaseModel):
    races: list[dict[str, Any]]


class SrdEquipmentResponse(BaseModel):
    equipment: dict[str, Any]


class SrdSpellsResponse(BaseModel):
    spells: list[dict[str, Any]]
