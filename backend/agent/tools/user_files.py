from langchain_core.tools import tool
from langgraph.config import get_config
from qdrant_client.http.models import FieldCondition, Filter, MatchAny, MatchValue

from backend.agent.utils.rag import vector_store


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
