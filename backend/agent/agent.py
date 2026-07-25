from langgraph.graph.state import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from .utils.nodes import chat_node
from .utils.state import MessagesState
from backend.core import settings

if settings.agent.is_in_memory:
    checkpointer = InMemorySaver()
    store = InMemoryStore()
else:
    # TODO: change to real storages
    checkpointer = InMemorySaver()
    store = InMemoryStore()

builder = StateGraph(MessagesState)

# Nodes
builder.add_node(chat_node, "chat_node")

# Edges
builder.set_entry_point("chat_node")
builder.set_finish_point("chat_node")

# Compile
agent = builder.compile(
    checkpointer=checkpointer,
    store=store,
)
