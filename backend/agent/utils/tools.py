from langchain_core.tools import create_retriever_tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from backend.agent.utils.rag import _get_retriever
from backend.core import settings

rag_tool = create_retriever_tool(
    retriever=_get_retriever(),
    name="search_knowledge_base",
    description="Find official information, documents and instructions from knowledge base. Use always when user asking specific information about something, or when user asking about it directly.",
)
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
)


async def get_tools_list() -> list:
    mcp_tools = await mcp_client.get_tools()
    return [rag_tool, *mcp_tools]
