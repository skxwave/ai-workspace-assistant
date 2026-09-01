import asyncio
import hashlib
import json
import logging

from langchain_core.tools import BaseTool
from mcp.types import Tool as McpTool
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .base import IntegrationProvider
from .interceptors import default_chain
from .local_cache import TtlLruCache
from .mcp_client import (
    authenticated_connection,
    discover_tool_definitions,
    hydrate_tools,
)
from .registry import IntegrationRegistry

logger = logging.getLogger(__name__)

SCHEMA_KEY = "mcp:schema:{key}"
LOCK_KEY = "mcp:schema:lock:{key}"

PEER_POLL_ATTEMPTS = 10
PEER_POLL_INTERVAL = 0.25
LOCK_TTL_SECONDS = 30


class SchemaCache:
    """Tool definitions per integration, shared by every tenant and worker.

    A hosted MCP server exposes the same catalogue to everyone, so discovery
    runs once per integration per TTL rather than once per request. Definitions
    live in Redis for the whole fleet and are fronted by a process-local LRU;
    hydration into LangChain tools is CPU-only and credential-free.
    """

    def __init__(
        self,
        registry: IntegrationRegistry,
        redis: Redis,
        *,
        ttl_seconds: int,
        refresh_interval_seconds: int,
        max_entries: int,
        discovery_tokens: dict[str, str],
    ) -> None:
        self._registry = registry
        self._redis = redis
        self._ttl_seconds = ttl_seconds
        self._refresh_interval_seconds = refresh_interval_seconds
        self._discovery_tokens = discovery_tokens
        self._local: TtlLruCache[list[BaseTool]] = TtlLruCache(max_entries)
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, provider: IntegrationProvider, token: str) -> list[BaseTool]:
        key = self._key(provider, token)
        cached = self._local.get(key)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            cached = self._local.get(key)
            if cached is not None:
                return cached
            definitions = await self._resolve_definitions(key, provider, token)
            return self._store(key, provider, definitions)

    async def refresh(self, provider: IntegrationProvider, token: str) -> list[BaseTool]:
        key = self._key(provider, token)
        async with self._lock_for(key):
            definitions = await self._discover(provider, token)
            await self._write_redis(key, definitions)
            return self._store(key, provider, definitions)

    async def run_refresh_loop(self) -> None:
        """Keep fleet-wide schemas warm so no user request pays for discovery.

        Only integrations with a configured discovery credential are refreshed
        here; the rest are seeded lazily from an inbound request, which is never
        retained.
        """
        while True:
            await asyncio.sleep(self._refresh_interval_seconds)
            for provider in self._registry:
                token = self._discovery_tokens.get(provider.name)
                if not token or provider.per_user_schema:
                    continue
                try:
                    await self.refresh(provider, token)
                except Exception:
                    logger.exception("Scheduled schema refresh failed for %s", provider.name)

    def _key(self, provider: IntegrationProvider, token: str) -> str:
        if not provider.per_user_schema:
            return provider.name
        return f"{provider.name}:{_fingerprint(token)}"

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _seed_token(self, provider: IntegrationProvider, token: str) -> str:
        if provider.per_user_schema:
            return token
        return self._discovery_tokens.get(provider.name) or token

    def _store(
        self,
        key: str,
        provider: IntegrationProvider,
        definitions: list[McpTool],
    ) -> list[BaseTool]:
        tools = hydrate_tools(
            definitions,
            connection=provider.build_connection(),
            server_name=provider.name,
            interceptors=default_chain(self._registry, provider),
            tool_name_prefix=provider.tool_name_prefix,
        )
        self._local.set(key, tools, self._ttl_seconds)
        return tools

    async def _resolve_definitions(
        self,
        key: str,
        provider: IntegrationProvider,
        token: str,
    ) -> list[McpTool]:
        definitions = await self._read_redis(key)
        if definitions is not None:
            return definitions

        if await self._acquire_redis_lock(key):
            try:
                definitions = await self._discover(provider, token)
                await self._write_redis(key, definitions)
                return definitions
            finally:
                await self._release_redis_lock(key)

        definitions = await self._await_peer(key)
        if definitions is not None:
            return definitions
        return await self._discover(provider, token)

    async def _discover(
        self,
        provider: IntegrationProvider,
        token: str,
    ) -> list[McpTool]:
        connection = authenticated_connection(
            provider.build_connection(),
            provider.auth_header(self._seed_token(provider, token)),
        )
        definitions = await discover_tool_definitions(connection)
        logger.info("Discovered %d tools for %s", len(definitions), provider.name)
        return definitions

    async def _await_peer(self, key: str) -> list[McpTool] | None:
        for _ in range(PEER_POLL_ATTEMPTS):
            await asyncio.sleep(PEER_POLL_INTERVAL)
            definitions = await self._read_redis(key)
            if definitions is not None:
                return definitions
        return None

    async def _read_redis(self, key: str) -> list[McpTool] | None:
        try:
            raw = await self._redis.get(SCHEMA_KEY.format(key=key))
        except RedisError:
            logger.warning("Redis unavailable while reading %s schema", key)
            return None
        if not raw:
            return None
        try:
            return [McpTool.model_validate(item) for item in json.loads(raw)]
        except (ValueError, TypeError):
            logger.warning("Discarding unreadable cached schema for %s", key)
            return None

    async def _write_redis(self, key: str, definitions: list[McpTool]) -> None:
        payload = json.dumps([item.model_dump(mode="json") for item in definitions])
        try:
            await self._redis.set(
                SCHEMA_KEY.format(key=key),
                payload,
                ex=self._ttl_seconds,
            )
        except RedisError:
            logger.warning("Redis unavailable while caching %s schema", key)

    async def _acquire_redis_lock(self, key: str) -> bool:
        try:
            acquired = await self._redis.set(
                LOCK_KEY.format(key=key),
                "1",
                nx=True,
                ex=LOCK_TTL_SECONDS,
            )
        except RedisError:
            return True
        return bool(acquired)

    async def _release_redis_lock(self, key: str) -> None:
        try:
            await self._redis.delete(LOCK_KEY.format(key=key))
        except RedisError:
            pass


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]
