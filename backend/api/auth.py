from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
import httpx

from backend.core import settings
from backend.auth.dependencies import get_current_active_user, oauth2_scheme
from backend.auth.schemas import RefreshRequest, TokenPair, UserCreate, UserRead
from backend.core.models.user import User
from backend.core.repositories.user_integration import UserIntegrationRepository, get_user_integration_repository
from backend.core.services import AuthService, get_auth_service

router = APIRouter(tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    user = await auth_service.register_user(
        payload.email,
        payload.password,
        payload.full_name,
    )
    return auth_service.issue_token_pair(user)


@router.post("/login", response_model=TokenPair)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    user = await auth_service.authenticate_user(
        form_data.username,
        form_data.password,
    )
    return auth_service.issue_token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await auth_service.rotate_refresh_token(payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    access_token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    await auth_service.revoke_token_pair(access_token, payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


@router.get("/github/auth_url")
async def get_github_url(current_user: Annotated[User, Depends(get_current_active_user)]):
    return {
        "url": f"https://github.com/login/oauth/authorize?client_id={settings.tools.github_client_id}&redirect_uri={settings.tools.github_redirect_uri}&scope=repo,user&state={current_user.id}"
    }


@router.get("/github/callback")
async def github_callback(
    integration_repo: Annotated[UserIntegrationRepository, Depends(get_user_integration_repository)],
    code: str = Query(),
    state: str = Query(),
):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.tools.github_client_id,
                "client_secret": settings.tools.github_client_secret,
                "code": code,
                "redirect_uri": settings.tools.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

        data = response.json()
        access_token = data.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Failed to retrieve token from GitHub",
            )

        # TODO: encrypt before storing
        await integration_repo.save_github_token(state, access_token)

        return {
            "status": "ok",
            "message": "GitHub successfully connected!",
            "access_token": access_token,
        }
