from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.messages import AIMessage, AIMessageChunk
from langchain_core.messages import BaseMessage, ToolMessage

EventType = Literal[
    "token",
    "tool_call",
    "tool_result",
    "confirmation_required",
    "end",
    "error",
]

RESULT_PREVIEW_CHARS = 300


@dataclass(frozen=True, slots=True)
class StreamEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    def as_frame(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data}


def token_event(content: str) -> StreamEvent:
    return StreamEvent("token", {"content": content})


def end_event() -> StreamEvent:
    return StreamEvent("end")


def error_event(detail: str) -> StreamEvent:
    return StreamEvent("error", {"detail": detail})


def graph_events(chunk: dict) -> Iterator[StreamEvent]:
    """Translate one `astream(version="v2")` chunk into transport-agnostic events."""
    if chunk["type"] == "messages":
        message, _ = chunk["data"]
        yield from _token_events(message)
    elif chunk["type"] == "updates":
        yield from _update_events(chunk["data"])


def _token_events(message: BaseMessage) -> Iterator[StreamEvent]:
    if isinstance(message, (AIMessage, AIMessageChunk)) and message.text:
        yield token_event(message.text)


def _update_events(update: dict) -> Iterator[StreamEvent]:
    for node, payload in update.items():
        if node == "__interrupt__":
            yield from _interrupt_events(payload)
        elif isinstance(payload, dict):
            yield from _message_events(payload.get("messages") or ())


def _interrupt_events(interrupts: Any) -> Iterator[StreamEvent]:
    for item in interrupts or ():
        if isinstance(item.value, dict):
            yield StreamEvent(
                "confirmation_required",
                {"calls": list(item.value.get("calls", ()))},
            )


def _message_events(messages: Any) -> Iterator[StreamEvent]:
    for message in messages:
        if isinstance(message, ToolMessage):
            yield StreamEvent("tool_result", _result_data(message))
        elif isinstance(message, AIMessage):
            for call in message.tool_calls:
                yield StreamEvent("tool_call", dict(call))


def _result_data(message: ToolMessage) -> dict[str, Any]:
    content = message.text
    return {
        "id": message.tool_call_id,
        "name": message.name,
        "status": message.status,
        "size": len(content),
        "preview": content[:RESULT_PREVIEW_CHARS],
    }
