from typing import Any, Protocol

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.interceptors import ToolCallInterceptor
from langchain_mcp_adapters.sessions import Connection, create_session
from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp import ClientSession
from mcp.types import Tool as McpTool

MAX_TOOL_PAGES = 100


class ToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None, **kw: Any): ...


def authenticated_connection(
    connection: Connection,
    headers: dict[str, str],
) -> Connection:
    merged = dict(connection)
    merged["headers"] = {**merged.get("headers", {}), **headers}
    return merged


async def _paginate_tools(session: ClientSession) -> list[McpTool]:
    definitions: list[McpTool] = []
    cursor: str | None = None

    for _ in range(MAX_TOOL_PAGES):
        page = await session.list_tools(cursor=cursor)
        definitions.extend(page.tools)
        if not page.nextCursor:
            return definitions
        cursor = page.nextCursor

    raise RuntimeError(f"Exceeded {MAX_TOOL_PAGES} pages while listing MCP tools")


async def discover_tool_definitions(connection: Connection) -> list[McpTool]:
    """One MCP handshake plus a paginated tools/list against a server."""
    async with create_session(connection) as session:
        await session.initialize()
        return await _paginate_tools(session)


def hydrate_tools(
    definitions: list[McpTool],
    *,
    server_name: str,
    interceptors: list[ToolCallInterceptor],
    tool_name_prefix: bool,
    session: ToolSession,
) -> list[BaseTool]:
    """Bind cached definitions to an already-authenticated MCP session."""
    return [
        convert_mcp_tool_to_langchain_tool(
            session,
            definition,
            tool_interceptors=interceptors,
            server_name=server_name,
            tool_name_prefix=tool_name_prefix,
        )
        for definition in definitions
    ]
