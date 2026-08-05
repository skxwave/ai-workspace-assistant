import uuid
from datetime import datetime, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.blacklist import blacklist_token, is_blacklisted
from backend.auth.schemas import TokenPair
from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.core.db import get_db
from backend.core.models.user import User

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> User | None:
        try:
            return await self.session.get(User, uuid.UUID(user_id))
        except ValueError:
            return None

    async def register_user(self, email: str, password: str, full_name: str | None) -> User:
        if await self.get_user_by_email(email):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

        user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        await self.session.refresh(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.get_user_by_email(email)
        if (
            not user
            or not user.hashed_password
            or not verify_password(password, user.hashed_password)
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
        return user

    def issue_token_pair(self, user: User) -> TokenPair:
        access, _, _ = create_access_token(user.id)
        refresh, _, _ = create_refresh_token(user.id)
        return TokenPair(access_token=access, refresh_token=refresh)

    async def rotate_refresh_token(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            raise credentials_exception

        if payload.get("type") != "refresh":
            raise credentials_exception
        if await is_blacklisted(payload["jti"]):
            raise credentials_exception

        user = await self.get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            raise credentials_exception

        # Rotation: the old refresh token is single-use — blacklist it so a
        # stolen/replayed copy can't be exchanged again.
        await blacklist_token(
            payload["jti"], datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        )
        return self.issue_token_pair(user)

    async def revoke_token_pair(self, access_token: str, refresh_token: str) -> None:
        for token in (access_token, refresh_token):
            try:
                payload = decode_token(token)
            except jwt.PyJWTError:
                continue
            await blacklist_token(
                payload["jti"], datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            )


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    return AuthService(session)
