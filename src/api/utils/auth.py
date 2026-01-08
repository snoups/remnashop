import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import jwt
from loguru import logger


def verify_telegram_auth(data: dict, bot_token: str, max_age_seconds: int = 86400) -> bool:
    """
    Проверка данных авторизации Telegram Login Widget.
    
    1. Создаём data-check-string из всех полей кроме 'hash'
    2. Создаём secret_key = SHA256(bot_token)
    3. Создаём hash = HMAC-SHA256(data_check_string, secret_key)
    4. Сравниваем с полученным hash
    """
    data_copy = data.copy()
    received_hash = data_copy.pop("hash", None)
    
    if not received_hash:
        logger.warning("Telegram auth: отсутствует hash")
        return False
    
    auth_date = data_copy.get("auth_date", 0)
    if isinstance(auth_date, str):
        auth_date = int(auth_date)
    
    now = datetime.now(timezone.utc)
    auth_datetime = datetime.fromtimestamp(auth_date, timezone.utc)
    
    if (now - auth_datetime).total_seconds() > max_age_seconds:
        logger.warning(f"Telegram auth: данные устарели (auth_date: {auth_date})")
        return False
    
    data_check_arr = [f"{k}={v}" for k, v in sorted(data_copy.items()) if v is not None]
    data_check_string = "\n".join(data_check_arr)
    
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    is_valid = computed_hash == received_hash
    
    if not is_valid:
        logger.warning("Telegram auth: неверный hash")
    
    return is_valid


def create_jwt_token(
    telegram_id: int,
    secret: str,
    expires_hours: int = 24
) -> tuple[str, datetime]:
    """Создание JWT токена для авторизованного пользователя."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    
    payload = {
        "sub": str(telegram_id),
        "jti": str(uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
        "type": "website_access"
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, expires_at


def verify_jwt_token(token: str, secret: str) -> Optional[int]:
    """Проверка JWT токена и возврат telegram_id."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        
        if payload.get("type") != "website_access":
            logger.warning("JWT: неверный тип токена")
            return None
        
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT: токен истёк")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT: невалидный токен - {e}")
        return None
