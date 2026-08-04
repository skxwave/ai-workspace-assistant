from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import service
from backend.auth.dependencies import get_current_active_user, oauth2_scheme
from backend.auth.schemas import RefreshRequest, TokenPair, UserCreate, UserRead
from backend.core.db import get_db
from backend.core.models.user import User

router = APIRouter(tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await service.register_user(
        session, payload.email, payload.password, payload.full_name
    )
    return service.issue_token_pair(user)


@router.post("/login", response_model=TokenPair)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await service.authenticate_user(
        session,
        form_data.username,
        form_data.password,
    )
    return service.issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await service.rotate_refresh_token(session, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    access_token: Annotated[str, Depends(oauth2_scheme)],
):
    await service.revoke_token_pair(access_token, payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user
