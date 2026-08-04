from datetime import datetime, timezone

from backend.core.redis import redis_client

_PREFIX = "blacklist:"


async def blacklist_token(jti: str, expires_at: datetime) -> None:
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl > 0:
        await redis_client.set(f"{_PREFIX}{jti}", "1", ex=ttl)


async def is_blacklisted(jti: str) -> bool:
    return await redis_client.exists(f"{_PREFIX}{jti}") == 1
