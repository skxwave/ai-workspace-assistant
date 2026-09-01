from langchain_mcp_adapters.interceptors import ToolCallInterceptor

from ..base import IntegrationProvider
from ..registry import IntegrationRegistry
from .response_trim import JsonFieldStripInterceptor, strip_fields
from .retry import RetryOn429Interceptor
from .token_injection import INTEGRATION_TOKENS_KEY, TokenInjectionInterceptor


def default_chain(
    registry: IntegrationRegistry,
    provider: IntegrationProvider,
) -> list[ToolCallInterceptor]:
    """Interceptor chain for one provider's tools, outermost first."""
    return [
        RetryOn429Interceptor(),
        TokenInjectionInterceptor(registry),
        *provider.response_interceptors,
    ]


__all__ = [
    "INTEGRATION_TOKENS_KEY",
    "JsonFieldStripInterceptor",
    "RetryOn429Interceptor",
    "TokenInjectionInterceptor",
    "default_chain",
    "strip_fields",
]
