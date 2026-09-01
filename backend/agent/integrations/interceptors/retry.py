import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx
from langchain_mcp_adapters.interceptors import MCPToolCallRequest, MCPToolCallResult

Handler = Callable[[MCPToolCallRequest], Awaitable[MCPToolCallResult]]


class RetryOn429Interceptor:
    """Retry an MCP tool call that hits the server's rate limit, with backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Handler,
    ) -> MCPToolCallResult:
        for attempt in range(self.max_retries + 1):
            try:
                return await handler(request)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt == self.max_retries:
                    raise
                retry_after = exc.response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after
                    else self.base_delay * (2**attempt)
                )
                delay += random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay)
