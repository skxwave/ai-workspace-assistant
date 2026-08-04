import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.core import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": expire,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)
    return token, jti, expire


def create_access_token(user_id: uuid.UUID) -> tuple[str, str, datetime]:
    return _create_token(
        str(user_id), "access", timedelta(minutes=settings.auth.access_token_expire_minutes)
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str, datetime]:
    return _create_token(
        str(user_id), "refresh", timedelta(days=settings.auth.refresh_token_expire_days)
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.auth.secret_key, algorithms=[settings.auth.algorithm])
