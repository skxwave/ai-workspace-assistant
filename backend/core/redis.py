import redis.asyncio as redis

from backend.core import settings

redis_client = redis.Redis(
    host=settings.db.redis.host,
    port=settings.db.redis.port,
    password=settings.db.redis.password,
    decode_responses=True,
)
