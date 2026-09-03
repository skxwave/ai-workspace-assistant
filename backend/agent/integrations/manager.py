import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.sessions import Connection, create_session

from backend.core.constants import IntegrationStatus

from .base import IntegrationProvider, IntegrationState
from .errors import is_auth_failure
from .health import IntegrationHealth
from .interceptors import session_chain
from .mcp_client import authenticated_connection, hydrate_tools
from .registry import IntegrationRegistry
from .schema_cache import SchemaCache

logger = logging.getLogger(__name__)


class _LazySession:
    """Opens and initializes the MCP session on the first tool call, then reuses it.

    A request that never invokes a tool pays no MCP handshake.
    """

    def __init__(
        self, stack: AsyncExitStack, connection: Connection, timeout: float
    ) -> None:
        self._stack = stack
        self._connection = connection
        self._timeout = timeout
        self._session: Any = None
        self._lock = asyncio.Lock()

    async def call_tool(self, *args: Any, **kwargs: Any):
        if self._session is None:
            async with self._lock:
                if self._session is None:
                    async with asyncio.timeout(self._timeout):
                        session = await self._stack.enter_async_context(
                            create_session(self._connection)
                        )
                        await session.initialize()
                    self._session = session
        return await self._session.call_tool(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class ToolBundle:
    tools: list[BaseTool]
    integrations: tuple[IntegrationState, ...]

    def with_status(self, status: IntegrationStatus) -> list[str]:
        return [state.name for state in self.integrations if state.status is status]


class McpToolManager:
    """Resolves the tool set a request may use.

    First-party tools are always present. Each connected, healthy integration
    contributes its allowlisted tools bound to one lazily-opened MCP session,
    shared by every tool call in the request. Failures degrade that
    integration alone.
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

    @asynccontextmanager
    async def open_tools(self, tokens: dict[str, str]) -> AsyncIterator[ToolBundle]:
        tools = list(self._first_party_tools)
        seen = {tool.name for tool in tools}
        states: list[IntegrationState] = []

        async with AsyncExitStack() as stack:
            for provider in self._registry:
                status, provider_tools = await self._enter(
                    stack, provider, tokens.get(provider.name)
                )
                states.append(IntegrationState(provider.name, status))
                accepted = self._deduplicate(provider, provider_tools, seen)
                tools.extend(sorted(accepted, key=lambda tool: tool.name))

            yield ToolBundle(tools=tools, integrations=tuple(states))

    async def _enter(
        self,
        stack: AsyncExitStack,
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
                    tools = await self._bind(stack, provider, token)
        except Exception as error:
            if is_auth_failure(error):
                logger.warning(
                    "%s rejected the stored token for this user", provider.name
                )
                return IntegrationStatus.EXPIRED, []
            self._health.record_failure(provider.name)
            logger.exception("Could not open %s tools", provider.name)
            return IntegrationStatus.DEGRADED, []

        self._health.record_success(provider.name)
        return IntegrationStatus.CONNECTED, tools

    async def _bind(
        self,
        stack: AsyncExitStack,
        provider: IntegrationProvider,
        token: str,
    ) -> list[BaseTool]:
        definitions = await self._schema_cache.definitions(provider, token)
        if provider.tool_allowlist:
            definitions = [
                d for d in definitions if d.name in provider.tool_allowlist
            ]
        connection = authenticated_connection(
            provider.build_connection(), provider.auth_header(token)
        )
        session = _LazySession(stack, connection, provider.discovery_timeout)
        return hydrate_tools(
            definitions,
            server_name=provider.name,
            interceptors=session_chain(provider),
            tool_name_prefix=provider.tool_name_prefix,
            session=session,
        )

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
