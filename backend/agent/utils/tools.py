import asyncio
import random

import httpx
from langchain_core.tools import create_retriever_tool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_config
from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue

from backend.agent.utils.rag import _get_retriever, vector_store
from backend.core import settings

knowledge_base_tool = create_retriever_tool(
    retriever=_get_retriever(),
    name="search_knowledge_base",
    description="Search the internal knowledge base for official internal documents, policies, and instructions. Use this for general company/org-wide knowledge — not for files the user has personally uploaded to this conversation (use search_my_uploads for those).",
)


@tool
async def search_user_files(query: str, file_ids: list[str] | None = None) -> str:
    """Search files uploaded by the user. 
    Use this tool when the user asks questions about their uploaded documents.
    
    Arguments:
        query: Search query phrase or keywords.
        file_ids: Optional list of specific file IDs to search within. Leave empty to search all user files.
    """
    thread_id = str(get_config()["configurable"]["thread_id"])
    must_conditions = [
        FieldCondition(key="metadata.owner_id", match=MatchValue(value=thread_id))
    ]

    if file_ids:
        must_conditions.append(
            FieldCondition(
                key="metadata.file_id", 
                match=MatchAny(any=file_ids)
            )
        )

    results = await vector_store.asimilarity_search(
        query,
        k=4,
        filter=Filter(must=must_conditions),
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


_tools_cache: list | None = None
_tools_cache_lock = asyncio.Lock()


async def get_tools_list() -> list:
    """Cached for the process lifetime so agent.py and chat_node share one tool list."""
    global _tools_cache
    if _tools_cache is None:
        async with _tools_cache_lock:
            if _tools_cache is None:
                mcp_tools = await mcp_client.get_tools()
                _tools_cache = [knowledge_base_tool, search_user_files, *mcp_tools]
    return _tools_cache
