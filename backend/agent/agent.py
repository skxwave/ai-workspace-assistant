from langgraph.graph.state import StateGraph

from .utils.nodes import chat_node
from .utils.state import MessagesState

builder = StateGraph(MessagesState)

# Nodes
builder.add_node(chat_node, "chat_node")

# Edges
builder.set_entry_point("chat_node")
builder.set_finish_point("chat_node")

# Compile
agent = builder.compile()
