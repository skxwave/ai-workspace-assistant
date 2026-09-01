from langchain_mcp_adapters.sessions import Connection

from ..base import IntegrationProvider
from ..interceptors import JsonFieldStripInterceptor

NAME = "github"

NOISE_FIELDS = frozenset(
    {"sha", "url", "git_url", "html_url", "download_url", "_links"}
)


def build_connection() -> Connection:
    return {
        "transport": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {
            "Accept": "text/event-stream",
            "User-Agent": "AI-Workspace-Assistant/1.0",
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
)
