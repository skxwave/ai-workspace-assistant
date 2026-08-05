from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.core.models.user import User
from backend.core.services.auth import AuthService, credentials_exception, get_auth_service

from .blacklist import is_blacklisted
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception
    if await is_blacklisted(payload["jti"]):
        raise credentials_exception

    user = await auth_service.get_user_by_id(payload["sub"])
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


async def require_superuser(user: Annotated[User, Depends(get_current_active_user)]) -> User:
    if not user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user
