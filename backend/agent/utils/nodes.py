from langchain_core.messages import RemoveMessage, SystemMessage, ToolMessage, trim_messages
from langchain_core.runnables import Runnable
from langgraph.graph import END

from backend.agent.utils.state import MessagesState

from .llms import openai_llm, summarize_llm

trimmer = trim_messages(
    max_tokens=2000,
    strategy="last",
    token_counter=openai_llm,
    include_system=True,
    allow_partial=False,
    start_on="human",
)


def make_chat_node(llm_chain: Runnable):
    async def chat_node(state: MessagesState) -> dict:
        trimmed_messages = await trimmer.ainvoke(state["messages"])
        response = await llm_chain.ainvoke({"messages": trimmed_messages})
        return {"messages": [response]}

    return chat_node


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
    if len(state["messages"]) > 10:
        return "summarize_node"
    return END
