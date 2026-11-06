"""
Авторизация: хеширование паролей (bcrypt) + JWT токены.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72


def hash_password(password: str) -> str:
    """Хешировать пароль через bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Проверить пароль против хеша."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    """Создать JWT токен с jti для возможной инвалидации."""
    payload = {
        "sub": user_id,
        "jti": uuid.uuid4().hex,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Декодировать JWT токен. Кидает исключение если невалиден."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


def new_id() -> str:
    return uuid.uuid4().hex  # полный UUID (32 hex-символа)
