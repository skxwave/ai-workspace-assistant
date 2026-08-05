from langchain_core.messages import AIMessage, RemoveMessage, SystemMessage, ToolMessage, trim_messages
from langgraph.graph import END

from backend.agent.utils.state import MessagesState
from backend.agent.utils.tools import get_tools_list

from .llms import openai_llm, summarize_llm, build_llm_chain, openai_llm

trimmer = trim_messages(
    max_tokens=16000,
    strategy="last",
    token_counter=openai_llm,
    include_system=True,
    allow_partial=False,
    start_on="human",
)


async def chat_node(state: MessagesState) -> dict:
    trimmed_messages = await trimmer.ainvoke(state["messages"])

    summary = state.get("summary", "")
    if summary:
        trimmed_messages = [
            SystemMessage(content=f"Summary of earlier conversation:\n{summary}")
        ] + trimmed_messages

    files = state.get("attached_file_ids", None)
    if files:
        trimmed_messages = [
            SystemMessage(
                content=f"User uploaded new files (ids: {files}), please use "
                f"`search_user_files` with file_ids={files} to look them up."
            )
        ] + trimmed_messages

    tools = await get_tools_list()
    llm_chain = build_llm_chain(llm=openai_llm, tools=tools)

    response = await llm_chain.ainvoke({"messages": trimmed_messages})
    return {"messages": [response], "attached_file_ids": None}


async def summarize_node(state: MessagesState) -> dict:
    summary = state.get("summary", "")
    messages = state["messages"]

    if len(messages) < 10:
        return {}

    cut = min(6, len(messages))
    while cut < len(messages) and isinstance(messages[cut], ToolMessage):
        cut += 1
    messages_to_summarize = messages[:cut]

    if summary:
        summary_prompt = (
            f"Here is previous summary of chat: {summary}\n\n"
            "Update this short summary depending on new messages:"
        )
    else:
        summary_prompt = "Create short concise summary from this chat history:"

    response = await summarize_llm.ainvoke(
        [SystemMessage(content=summary_prompt)] + messages_to_summarize
    )
    new_summary = response.content
    delete_messages = [RemoveMessage(id=m.id) for m in messages_to_summarize if m.id]

    return {
        "summary": new_summary,
        "messages": delete_messages
    }


def should_summarize(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return END

    if len(messages) > 20:
        return "summarize_node"
    return END
