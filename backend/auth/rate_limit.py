from fastapi import HTTPException, Request, status

from backend.core.redis import redis_client

_PREFIX = "ratelimit:"


def rate_limit(key: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        identifier = request.client.host if request.client else "unknown"
        redis_key = f"{_PREFIX}{key}:{identifier}"
        count = await redis_client.incr(redis_key)
        if count == 1:
            await redis_client.expire(redis_key, window_seconds)
        if count > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, try again later",
            )

    return dependency
