from langchain_core.messages import AIMessage, ToolMessage

DECLINED = (
    "The user declined this action, so it was not performed. Do not retry it; "
    "tell them what you skipped and ask how they want to proceed."
)


def pending_confirmations(
    message: AIMessage,
    confirm_tools: frozenset[str],
) -> list[dict]:
    return [
        {"id": call["id"], "name": call["name"], "args": call["args"]}
        for call in message.tool_calls
        if call["name"] in confirm_tools
    ]


def declined_messages(message: AIMessage) -> list[ToolMessage]:
    return [
        ToolMessage(content=DECLINED, tool_call_id=call["id"], name=call["name"])
        for call in message.tool_calls
    ]
