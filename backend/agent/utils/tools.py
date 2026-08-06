import asyncio
import json
import logging
import random

import httpx
from langchain_core.tools import create_retriever_tool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.config import get_config
from mcp.types import CallToolResult, TextContent
from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue

from backend.agent.utils.rag import _get_retriever, vector_store
from backend.core import settings

logger = logging.getLogger(__name__)

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
            FieldCondition(key="metadata.file_id", match=MatchAny(any=file_ids))
        )

    results = await vector_store.asimilarity_search(
        query,
        k=4,
        filter=Filter(must=must_conditions),
    )
    if not results:
        return "No relevant results found."
    return "\n\n".join(
        f"[{doc.metadata.get('filename', 'uploaded file')}] {doc.page_content}"
        for doc in results
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
                delay = (
                    float(retry_after)
                    if retry_after
                    else self.base_delay * (2**attempt)
                )
                delay += random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay)


# GitHub's REST API responses include bookkeeping fields (sha, url, git_url,
# html_url, download_url, _links) on every file/dir entry. The model never
# references them, but they stay in message history until summarized away —
# stripping them here keeps every subsequent turn's prompt smaller.
_GITHUB_NOISE_FIELDS = {"sha", "url", "git_url", "html_url", "download_url", "_links"}


def _strip_fields(value, fields: set[str]):
    if isinstance(value, dict):
        return {
            k: _strip_fields(v, fields) for k, v in value.items() if k not in fields
        }
    if isinstance(value, list):
        return [_strip_fields(item, fields) for item in value]
    return value


class GithubResponseTrimInterceptor:
    """Strips GitHub API bookkeeping fields from `github` MCP tool results."""

    async def __call__(self, request, handler):
        result = await handler(request)
        if request.server_name != "github" or not isinstance(result, CallToolResult):
            return result

        new_content = []
        changed = False
        for block in result.content:
            if isinstance(block, TextContent):
                try:
                    data = json.loads(block.text)
                except json.JSONDecodeError, TypeError:
                    new_content.append(block)
                    continue
                trimmed = _strip_fields(data, _GITHUB_NOISE_FIELDS)
                block = block.model_copy(
                    update={"text": json.dumps(trimmed, separators=(",", ":"))}
                )
                changed = True
            new_content.append(block)

        return result.model_copy(update={"content": new_content}) if changed else result


# Easy to add new integrations
_INTEGRATION_SERVER_BUILDERS = {
    "github": lambda token: {
        "transport": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
            "User-Agent": "AI-Workspace-Assistant/1.0",
        },
        "timeout": 30.0,
    },
}


def get_user_mcp_client(tokens: dict[str, str]) -> MultiServerMCPClient | None:
    """Build an MCP client with only the servers the user has connected.

    `tokens` maps integration name (e.g. "github") to that user's access token.
    Integrations missing a token are left out entirely, so the model never
    sees tools it can't actually use.
    """
    servers = {
        name: build_config(tokens[name])
        for name, build_config in _INTEGRATION_SERVER_BUILDERS.items()
        if tokens.get(name)
    }
    if not servers:
        return None
    return MultiServerMCPClient(
        servers,
        tool_interceptors=[RetryOn429Interceptor(), GithubResponseTrimInterceptor()],
    )


_AUTH_STATUS_CODES = {401, 403}


def _is_auth_failure(
    error: BaseException | None,
    depth: int = 0,
) -> bool:
    """True if `error` was ultimately caused by rejected credentials"""
    if error is None or depth > 10:
        return False
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in _AUTH_STATUS_CODES
    if isinstance(error, BaseExceptionGroup):
        return any(_is_auth_failure(exc, depth + 1) for exc in error.exceptions)
    return _is_auth_failure(error.__cause__ or error.__context__, depth + 1)


async def _load_integration_tools(
    name: str,
    token: str,
) -> list:
    """Fetch one integration's MCP tools. Raises on failure."""
    client = MultiServerMCPClient(
        {name: _INTEGRATION_SERVER_BUILDERS[name](token)},
        tool_interceptors=[RetryOn429Interceptor(), GithubResponseTrimInterceptor()],
    )
    return await client.get_tools()


async def get_tools_list(tokens: dict[str, str]) -> tuple[list, list[str], list[str]]:
    """Get tools list for a user, plus the names of integrations they haven't connected.

    The missing list lets the agent proactively tell the user which
    integrations would unlock more tools, instead of silently having no
    access to them.
    """
    missing_integrations: list[str] = []
    expired_integrations: list[str] = []
    mcp_tools: list = []

    for name in _INTEGRATION_SERVER_BUILDERS:
        token = tokens.get(name)
        if not token:
            missing_integrations.append(name)
            continue

        try:
            mcp_tools.extend(await _load_integration_tools(name, token))
        except Exception as error:
            if _is_auth_failure(error):
                logger.warning("%s rejected the stored token for this user", name)
                expired_integrations.append(name)
            else:
                logger.exception("Could not load %s tools", name)
                missing_integrations.append(name)

    tools = [knowledge_base_tool, search_user_files, *mcp_tools]
    return tools, missing_integrations, expired_integrations
