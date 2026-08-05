import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return result.scalar()

    async def save_github_token(
        self,
        user_id: uuid.UUID,
        token: str,
    ) -> UserIntegration:
        result = await self.session.execute(
            select(UserIntegration).where(UserIntegration.user_id == user_id)
        )
        integration = result.scalar()

        if integration:
            integration.github_access_token = token
        else:
            integration = UserIntegration(
                user_id=user_id,
                github_access_token=token,
            )
            self.session.add(integration)

        await self.session.commit()
        return integration


def get_user_integration_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserIntegrationRepository:
    return UserIntegrationRepository(session)
