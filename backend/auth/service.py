import uuid
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models.user import User

from .blacklist import blacklist_token, is_blacklisted
from .schemas import TokenPair
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    try:
        return await session.get(User, uuid.UUID(user_id))
    except ValueError:
        return None


async def register_user(
    session: AsyncSession, email: str, password: str, full_name: str | None
) -> User:
    if await get_user_by_email(session, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


def issue_token_pair(user: User) -> TokenPair:
    access, _, _ = create_access_token(user.id)
    refresh, _, _ = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=refresh)


async def rotate_refresh_token(session: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception
    if await is_blacklisted(payload["jti"]):
        raise credentials_exception

    user = await get_user_by_id(session, payload["sub"])
    if not user or not user.is_active:
        raise credentials_exception

    # Rotation: the old refresh token is single-use — blacklist it so a
    # stolen/replayed copy can't be exchanged again.
    await blacklist_token(payload["jti"], datetime.fromtimestamp(payload["exp"], tz=timezone.utc))
    return issue_token_pair(user)


async def revoke_token_pair(access_token: str, refresh_token: str) -> None:
    for token in (access_token, refresh_token):
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            continue
        await blacklist_token(payload["jti"], datetime.fromtimestamp(payload["exp"], tz=timezone.utc))
