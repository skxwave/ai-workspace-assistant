from collections.abc import Awaitable, Callable

from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult
from langgraph.config import get_config

from ..registry import IntegrationRegistry

INTEGRATION_TOKENS_KEY = "integration_tokens"

Handler = Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]]


class TokenInjectionInterceptor:
    """Applies the calling user's credentials to a tool call.

    Cached tool definitions are shared across tenants and carry no credentials.
    The token for this invocation is read from the graph's `RunnableConfig` and
    applied as request headers, so isolation is per tool call.
    """

    def __init__(self, registry: IntegrationRegistry) -> None:
        self._registry = registry

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Handler,
    ) -> MCPToolCallResult:
        token = self._token_for(request.server_name)
        if token and self._registry.has(request.server_name):
            provider = self._registry.get(request.server_name)
            request = request.override(headers=provider.auth_header(token))
        return await handler(request)

    def _token_for(self, server_name: str) -> str | None:
        try:
            config = get_config()
        except RuntimeError:
            return None
        tokens = config.get("configurable", {}).get(INTEGRATION_TOKENS_KEY) or {}
        return tokens.get(server_name)
