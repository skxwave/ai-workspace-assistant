from fastapi import Request
from langgraph.graph.state import CompiledStateGraph, StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.memory import InMemoryStore

from backend.core import settings

from .memory.checkpointer import get_checkpointer
from .utils.nodes import chat_node, summarize_node, should_summarize
from .utils.state import MessagesState
from .utils.tools import get_tools_list


async def workflow():
    builder = StateGraph(MessagesState)

    tools = await get_tools_list()

    # Nodes
    builder.add_node(chat_node)
    builder.add_node(summarize_node, "summarize_node")
    builder.add_node("tools", ToolNode(tools))

    # Edges
    builder.set_entry_point("chat_node")
    builder.add_conditional_edges("chat_node", tools_condition)
    builder.add_conditional_edges("chat_node", should_summarize)
    builder.add_edge("summarize_node", END)
    builder.add_edge("tools", "chat_node")
    builder.set_finish_point("chat_node")

    return builder

# Compile
async def compile_graph() -> CompiledStateGraph:
    if settings.agent.is_in_memory:
        checkpointer = InMemorySaver()
        store = InMemoryStore()
    else:
        checkpointer = await get_checkpointer()
        # TODO: change to real storage
        store = InMemoryStore()

    builder = await workflow()
    agent = builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
    return agent


def get_agent(request: Request) -> CompiledStateGraph:
    """Dependency for FastAPI to retrieve agent"""
    return request.app.state.agent
