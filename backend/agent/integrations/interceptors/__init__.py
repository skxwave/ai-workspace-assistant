from langchain_mcp_adapters.interceptors import ToolCallInterceptor

from ..base import IntegrationProvider
from .response_trim import JsonFieldStripInterceptor, strip_fields
from .retry import RetryOn429Interceptor


def session_chain(provider: IntegrationProvider) -> list[ToolCallInterceptor]:
    """Interceptor chain for a provider's tools on a live session, outermost first."""
    return [RetryOn429Interceptor(), *provider.response_interceptors]


__all__ = [
    "JsonFieldStripInterceptor",
    "RetryOn429Interceptor",
    "session_chain",
    "strip_fields",
]
