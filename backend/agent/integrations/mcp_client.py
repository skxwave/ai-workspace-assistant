from langchain_core.tools import BaseTool
from langchain_mcp_adapters.interceptors import ToolCallInterceptor
from langchain_mcp_adapters.sessions import Connection, create_session
from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp import ClientSession
from mcp.types import Tool as McpTool

MAX_TOOL_PAGES = 100


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
    connection: Connection,
    server_name: str,
    interceptors: list[ToolCallInterceptor],
    tool_name_prefix: bool,
) -> list[BaseTool]:
    """Build LangChain tools from cached definitions. No network access.

    `connection` carries no credentials; each call's interceptor chain supplies
    the invoking user's token.
    """
    return [
        convert_mcp_tool_to_langchain_tool(
            None,
            definition,
            connection=connection,
            tool_interceptors=interceptors,
            server_name=server_name,
            tool_name_prefix=tool_name_prefix,
        )
        for definition in definitions
    ]
