import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult
from mcp.types import CallToolResult, TextContent

Handler = Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]]


def strip_fields(value: Any, fields: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_fields(item, fields)
            for key, item in value.items()
            if key not in fields
        }
    if isinstance(value, list):
        return [strip_fields(item, fields) for item in value]
    return value


class JsonFieldStripInterceptor:
    """Drops bookkeeping fields from one server's JSON tool results.

    Provider APIs return fields the model never references but which stay in
    message history until summarized away. Stripping them keeps every
    subsequent turn's prompt smaller.
    """

    def __init__(self, server_name: str, fields: frozenset[str]) -> None:
        self._server_name = server_name
        self._fields = fields

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Handler,
    ) -> MCPToolCallResult:
        result = await handler(request)
        if request.server_name != self._server_name or not isinstance(
            result, CallToolResult
        ):
            return result

        new_content = []
        changed = False
        for block in result.content:
            if isinstance(block, TextContent):
                try:
                    data = json.loads(block.text)
                except (json.JSONDecodeError, TypeError):
                    new_content.append(block)
                    continue
                trimmed = strip_fields(data, self._fields)
                block = block.model_copy(
                    update={"text": json.dumps(trimmed, separators=(",", ":"))}
                )
                changed = True
            new_content.append(block)

        return result.model_copy(update={"content": new_content}) if changed else result
