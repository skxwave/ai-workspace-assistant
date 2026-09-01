from langchain_core.tools import create_retriever_tool

from backend.agent.utils.rag import get_retriever

DESCRIPTION = (
    "Search the internal knowledge base for official internal documents, policies, "
    "and instructions. Use this for general company/org-wide knowledge — not for "
    "files the user has personally uploaded to this conversation (use "
    "search_user_files for those)."
)

knowledge_base_tool = create_retriever_tool(
    retriever=get_retriever(),
    name="search_knowledge_base",
    description=DESCRIPTION,
)
