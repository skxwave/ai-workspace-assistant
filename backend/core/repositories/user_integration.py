import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import decrypt_secret, encrypt_secret
from backend.core.db import get_db
from backend.core.models.user_integrations import UserIntegration


class UserIntegrationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_github_token(self, user_id: uuid.UUID) -> str | None:
        result = await self.session.execute(
            select(UserIntegration.github_access_token).where(
                UserIntegration.user_id == user_id
            )
        )
        encrypted_token = result.scalar()
        if encrypted_token is None:
            return None
        return decrypt_secret(encrypted_token)

    async def save_github_token(
        self,
        user_id: str | uuid.UUID,
        token: str,
    ) -> UserIntegration:
        encrypted_token = encrypt_secret(token)

        result = await self.session.execute(
            select(UserIntegration).where(UserIntegration.user_id == user_id)
        )
        integration = result.scalar()

        if integration:
            integration.github_access_token = encrypted_token
        else:
            integration = UserIntegration(
                user_id=user_id,
                github_access_token=encrypted_token,
            )
            self.session.add(integration)

        await self.session.commit()
        return integration

    async def clear_github_token(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(UserIntegration)
            .where(UserIntegration.user_id == user_id)
            .values(github_access_token=None)
        )
        await self.session.commit()


def get_user_integration_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserIntegrationRepository:
    return UserIntegrationRepository(session)
