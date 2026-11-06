"""Здоровье сервиса."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str = "3.0.0.21"
