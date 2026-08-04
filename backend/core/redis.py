import redis.asyncio as redis

from backend.core import settings

redis_client = redis.Redis(
    host=settings.db.redis.host,
    port=settings.db.redis.port,
    decode_responses=True,
)
