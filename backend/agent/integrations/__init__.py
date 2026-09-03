from backend.agent.tools import FIRST_PARTY_TOOLS
from backend.core import settings
from backend.core.constants import IntegrationStatus
from backend.core.redis import redis_client

from .base import IntegrationProvider, IntegrationState
from .health import IntegrationHealth
from .manager import McpToolManager, ToolBundle
from .providers import register_all
from .registry import integration_registry
from .schema_cache import SchemaCache

register_all(integration_registry)

integration_health = IntegrationHealth(
    failure_threshold=settings.integrations.failure_threshold,
    cooldown_seconds=settings.integrations.breaker_cooldown_seconds,
)

schema_cache = SchemaCache(
    integration_registry,
    redis_client,
    ttl_seconds=settings.integrations.schema_ttl_seconds,
    refresh_interval_seconds=settings.integrations.schema_refresh_interval_seconds,
    max_entries=settings.integrations.schema_cache_size,
    discovery_tokens=settings.integrations.discovery_tokens,
)

mcp_tool_manager = McpToolManager(
    integration_registry,
    schema_cache,
    integration_health,
    FIRST_PARTY_TOOLS,
)

__all__ = [
    "IntegrationProvider",
    "IntegrationState",
    "IntegrationStatus",
    "McpToolManager",
    "ToolBundle",
    "integration_health",
    "integration_registry",
    "mcp_tool_manager",
    "schema_cache",
]
