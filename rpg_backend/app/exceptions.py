class RPGException(Exception):
    """Базовое исключение приложения."""


class AIError(RPGException):
    """Ошибка при обращении к AI API."""


class ValidationError(RPGException):
    """Ошибка валидации входных данных."""


class RateLimitError(RPGException):
    """Превышен лимит запросов."""
