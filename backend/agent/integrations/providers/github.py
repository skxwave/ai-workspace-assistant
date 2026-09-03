from langchain_mcp_adapters.sessions import Connection

from backend.core import settings

from ..base import IntegrationProvider
from ..interceptors import JsonFieldStripInterceptor

NAME = "github"

NOISE_FIELDS = frozenset(
    {"sha", "url", "git_url", "html_url", "download_url", "_links"}
)

# Only the tools this assistant actually drives are bound to the model; the
# hosted server exposes ~40 and their schemas dominate every prompt.
TOOL_ALLOWLIST = frozenset(
    {
        "get_me",
        "get_file_contents",
        "list_branches",
        "create_branch",
        "create_or_update_file",
        "push_files",
        "list_commits",
        "get_commit",
        "list_pull_requests",
        "pull_request_read",
        "create_pull_request",
        "update_pull_request",
        "update_pull_request_branch",
        "merge_pull_request",
        "pull_request_review_write",
        "add_comment_to_pending_review",
        "list_issues",
        "issue_read",
        "issue_write",
        "add_issue_comment",
        "search_code",
        "search_repositories",
        "search_pull_requests",
        "search_issues",
    }
)


def build_connection() -> Connection:
    return {
        "transport": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {
            "Accept": "text/event-stream",
            "User-Agent": "AI-Workspace-Assistant/1.0",
            "X-MCP-Toolsets": ",".join(settings.tools.github_toolsets),
        },
        "timeout": 30.0,
    }


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


github_provider = IntegrationProvider(
    name=NAME,
    build_connection=build_connection,
    auth_header=auth_header,
    response_interceptors=(
        JsonFieldStripInterceptor(server_name=NAME, fields=NOISE_FIELDS),
    ),
    tool_allowlist=TOOL_ALLOWLIST,
)
