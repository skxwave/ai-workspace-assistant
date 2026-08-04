import asyncio
import random

import httpx
from langchain_core.tools import create_retriever_tool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_config
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from backend.agent.utils.rag import _get_retriever, vector_store
from backend.core import settings

knowledge_base_tool = create_retriever_tool(
    retriever=_get_retriever(),
    name="search_knowledge_base",
    description="Search the internal knowledge base for official internal documents, policies, and instructions. Use this for general company/org-wide knowledge — not for files the user has personally uploaded to this conversation (use search_my_uploads for those).",
)


@tool
async def search_my_uploads(query: str) -> str:
    """Search files the current user has uploaded to this conversation. Use this
    when the question refers to something like "my file", "the document I
    uploaded", or "the PDF I attached" — not for general company knowledge
    (use search_knowledge_base for that)."""
    thread_id = str(get_config()["configurable"]["thread_id"])
    results = await vector_store.asimilarity_search(
        query,
        k=3,
        filter=Filter(
            must=[FieldCondition(key="metadata.owner_id", match=MatchValue(value=thread_id))]
        ),
    )
    if not results:
        return "No relevant results found."
    return "\n\n".join(
        f"[{doc.metadata.get('filename', 'uploaded file')}] {doc.page_content}" for doc in results
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
    return [knowledge_base_tool, search_my_uploads, *mcp_tools]
