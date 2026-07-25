from langchain_core.tools import create_retriever_tool

from backend.agent.utils.rag import _get_retriever


rag_tool = create_retriever_tool(
    retriever=_get_retriever(),
    name="search_knowledge_base",
    description="Find official information, documents and instructions from knowledge base. Use always when user asking specific information about something, or when user asking about it directly.",
)


tools_list = [rag_tool]
