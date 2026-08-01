import asyncio
import random

import httpx
from langchain_core.tools import create_retriever_tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from backend.agent.utils.rag import _get_retriever
from backend.core import settings

rag_tool = create_retriever_tool(
    retriever=_get_retriever(),
    name="search_knowledge_base",
    description="Search the internal knowledge base for official internal documents, policies, and instructions. Only use this when the question is specifically about internal docs/policies that can't be answered from other tools or the current conversation.",
)


class RetryOn429Interceptor:
    """Retry an MCP tool call that hits the server's rate limit, with backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def __call__(self, request, handler):
        for attempt in range(self.max_retries + 1):
            try:
                return await handler(request)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt == self.max_retries:
                    raise
                retry_after = exc.response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else self.base_delay * (2**attempt)
                delay += random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay)


mcp_client = MultiServerMCPClient(
    {
        "github": {
            "transport": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {settings.tools.github_pat}",
                "Accept": "text/event-stream",
                "User-Agent": "AI-Workspace-Assistant/1.0",
            },
            "timeout": 30.0,
        },
    },
    tool_interceptors=[RetryOn429Interceptor()],
)


async def get_tools_list() -> list:
    mcp_tools = await mcp_client.get_tools()
    return [rag_tool, *mcp_tools]
