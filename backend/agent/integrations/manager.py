import asyncio
import logging
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from backend.core.constants import IntegrationStatus

from .base import IntegrationProvider, IntegrationState
from .errors import is_auth_failure
from .health import IntegrationHealth
from .registry import IntegrationRegistry
from .schema_cache import SchemaCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolBundle:
    tools: list[BaseTool]
    integrations: tuple[IntegrationState, ...]

    def with_status(self, status: IntegrationStatus) -> list[str]:
        return [state.name for state in self.integrations if state.status is status]


class McpToolManager:
    """Resolves the tool set a request may use.

    First-party tools are always present. Each registered integration
    contributes its cached tools when the user has connected it and the
    provider is healthy; failures degrade that integration alone.
    """

    def __init__(
        self,
        registry: IntegrationRegistry,
        schema_cache: SchemaCache,
        health: IntegrationHealth,
        first_party_tools: list[BaseTool],
    ) -> None:
        self._registry = registry
        self._schema_cache = schema_cache
        self._health = health
        self._first_party_tools = first_party_tools

    async def build_bundle(self, tokens: dict[str, str]) -> ToolBundle:
        providers = list(self._registry)
        resolved = await asyncio.gather(
            *(self._resolve(provider, tokens.get(provider.name)) for provider in providers),
            return_exceptions=True,
        )

        tools = list(self._first_party_tools)
        states: list[IntegrationState] = []
        seen = {tool.name for tool in tools}

        for provider, outcome in zip(providers, resolved, strict=True):
            if isinstance(outcome, BaseException):
                logger.exception(
                    "Resolving %s tools failed", provider.name, exc_info=outcome
                )
                states.append(IntegrationState(provider.name, IntegrationStatus.DEGRADED))
                continue
            status, provider_tools = outcome
            states.append(IntegrationState(provider.name, status))
            tools.extend(self._deduplicate(provider, provider_tools, seen))

        return ToolBundle(tools=tools, integrations=tuple(states))

    async def _resolve(
        self,
        provider: IntegrationProvider,
        token: str | None,
    ) -> tuple[IntegrationStatus, list[BaseTool]]:
        if not token:
            return IntegrationStatus.NOT_CONNECTED, []

        if not self._health.is_available(provider.name):
            return IntegrationStatus.DEGRADED, []

        try:
            async with self._health.limiter(provider):
                async with asyncio.timeout(provider.discovery_timeout):
                    tools = await self._schema_cache.get(provider, token)
        except Exception as error:
            if is_auth_failure(error):
                logger.warning("%s rejected the stored token for this user", provider.name)
                return IntegrationStatus.EXPIRED, []
            self._health.record_failure(provider.name)
            logger.exception("Could not load %s tools", provider.name)
            return IntegrationStatus.DEGRADED, []

        self._health.record_success(provider.name)
        return IntegrationStatus.CONNECTED, tools

    def _deduplicate(
        self,
        provider: IntegrationProvider,
        tools: list[BaseTool],
        seen: set[str],
    ) -> list[BaseTool]:
        accepted = []
        for tool in tools:
            if tool.name in seen:
                logger.warning(
                    "Dropping %s tool %r: name already provided by another integration",
                    provider.name,
                    tool.name,
                )
                continue
            seen.add(tool.name)
            accepted.append(tool)
        return accepted
