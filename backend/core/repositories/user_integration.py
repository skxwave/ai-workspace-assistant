import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import decrypt_secret, encrypt_secret
from backend.core.constants import IntegrationStatus
from backend.core.db import get_db
from backend.core.models.user_integrations import UserIntegration


class UserIntegrationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tokens(self, user_id: uuid.UUID) -> dict[str, str]:
        """Decrypted tokens for every integration the user has connected."""
        result = await self.session.execute(
            select(UserIntegration.provider, UserIntegration.encrypted_token).where(
                UserIntegration.user_id == user_id,
                UserIntegration.status == IntegrationStatus.CONNECTED,
            )
        )
        tokens = {}
        for provider, encrypted_token in result:
            token = decrypt_secret(encrypted_token)
            if token:
                tokens[provider] = token
        return tokens

    async def list_states(self, user_id: uuid.UUID) -> dict[str, IntegrationStatus]:
        result = await self.session.execute(
            select(UserIntegration.provider, UserIntegration.status).where(
                UserIntegration.user_id == user_id
            )
        )
        return {provider: IntegrationStatus(status) for provider, status in result}

    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: str,
        token: str,
        scopes: str | None = None,
    ) -> None:
        values = {
            "user_id": user_id,
            "provider": provider,
            "encrypted_token": encrypt_secret(token),
            "status": IntegrationStatus.CONNECTED,
            "scopes": scopes,
        }
        statement = insert(UserIntegration).values(**values)
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[UserIntegration.user_id, UserIntegration.provider],
                set_={
                    "encrypted_token": statement.excluded.encrypted_token,
                    "status": statement.excluded.status,
                    "scopes": statement.excluded.scopes,
                    "updated_at": func.now(),
                },
            )
        )
        await self.session.commit()

    async def set_status(
        self,
        user_id: uuid.UUID,
        provider: str,
        status: IntegrationStatus,
    ) -> None:
        await self.session.execute(
            update(UserIntegration)
            .where(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == provider,
            )
            .values(status=status, updated_at=func.now())
        )
        await self.session.commit()

    async def delete(self, user_id: uuid.UUID, provider: str) -> None:
        await self.session.execute(
            delete(UserIntegration).where(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == provider,
            )
        )
        await self.session.commit()


def get_user_integration_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserIntegrationRepository:
    return UserIntegrationRepository(session)
