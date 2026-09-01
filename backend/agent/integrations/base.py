from collections.abc import Callable
from dataclasses import dataclass

from langchain_mcp_adapters.interceptors import ToolCallInterceptor
from langchain_mcp_adapters.sessions import Connection

from backend.core.constants import IntegrationStatus


@dataclass(frozen=True, slots=True)
class IntegrationState:
    name: str
    status: IntegrationStatus


@dataclass(frozen=True, slots=True)
class IntegrationProvider:
    name: str
    build_connection: Callable[[], Connection]
    auth_header: Callable[[str], dict[str, str]]
    response_interceptors: tuple[ToolCallInterceptor, ...] = ()
    per_user_schema: bool = False
    tool_name_prefix: bool = False
    discovery_timeout: float = 20.0
    max_concurrency: int = 10
