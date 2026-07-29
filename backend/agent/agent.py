from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.memory import InMemoryStore

from backend.core import settings

from .memory.checkpointer import get_checkpointer
from .utils.nodes import chat_node
from .utils.state import MessagesState
from .utils.tools import tools_list

builder = StateGraph(MessagesState)

# Nodes
builder.add_node(chat_node, "chat_node")
builder.add_node("tools", ToolNode(tools_list))

# Edges
builder.set_entry_point("chat_node")
builder.add_conditional_edges("chat_node", tools_condition)
builder.add_edge("tools", "chat_node")
builder.set_finish_point("chat_node")

# Compile
async def get_agent() -> CompiledStateGraph:
    if settings.agent.is_in_memory:
        checkpointer = InMemorySaver()
        store = InMemoryStore()
    else:
        checkpointer = await get_checkpointer()
        # TODO: change to real storage
        store = InMemoryStore()

    agent = builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
    return agent
