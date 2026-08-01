from typing_extensions import TypedDict, Annotated

from langgraph.graph.message import add_messages


class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]
    summary: str
