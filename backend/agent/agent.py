import asyncio
import logging

from langchain_core.messages import (
    AIMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.memory import InMemoryStore

from backend.agent.memory import get_shared_checkpointer, get_shared_store
from backend.agent.utils.prompts import integration_notice, system_prompt_template
from backend.agent.utils.state import MessagesState
from backend.core import settings

logger = logging.getLogger(__name__)


class WorkspaceAgent:
    def __init__(self) -> None:
        self._chat_llm = self._create_llm(
            model=settings.llms.openai_gpt_5_4,
            temperature=0.8,
        )
        self._summarize_llm = self._create_llm(
            model=settings.llms.openai_gpt_5_mini,
            temperature=0.7,
        )

        self._trimmer = trim_messages(
            max_tokens=16000,
            strategy="last",
            token_counter=self._chat_llm,
            include_system=True,
            allow_partial=False,
            start_on="human",
        )

    def _create_llm(self, model: str, temperature: float) -> ChatOpenAI:
        return ChatOpenAI(
            model=model,
            base_url=settings.llms.openai_base_url,
            api_key=settings.llms.openai_api_key,
            temperature=temperature,
        )

    async def _chat_node(self, state: MessagesState, config: RunnableConfig) -> dict:
        configurable = config["configurable"]
        trimmed_messages = await self._trimmer.ainvoke(state["messages"])

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

        notice = integration_notice(configurable.get("integrations", ()))
        if notice:
            trimmed_messages = [SystemMessage(content=notice)] + trimmed_messages

        chain = system_prompt_template | self._chat_llm.bind_tools(
            tools=configurable["tools"]
        )
        response = await chain.ainvoke({"messages": trimmed_messages})
        return {"messages": [response], "attached_file_ids": None}

    async def _tools_node(self, state: MessagesState, config: RunnableConfig) -> dict:
        return await ToolNode(config["configurable"]["tools"]).ainvoke(state, config)

    async def _summarize_node(self, state: MessagesState) -> dict:
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

        response = await self._summarize_llm.ainvoke(
            [SystemMessage(content=summary_prompt)] + messages_to_summarize
        )
        new_summary = response.content
        delete_messages = [
            RemoveMessage(id=m.id) for m in messages_to_summarize if m.id
        ]

        return {"summary": new_summary, "messages": delete_messages}

    def _should_summarize(self, state: MessagesState) -> str:
        messages = state["messages"]
        last_message = messages[-1]

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return END

        if len(messages) > 20:
            return "summarize_node"
        return END

    async def build_graph(self) -> CompiledStateGraph:
        builder = StateGraph(MessagesState)

        builder.add_node("chat_node", self._chat_node)
        builder.add_node("summarize_node", self._summarize_node)
        builder.add_node("tools", self._tools_node)

        builder.set_entry_point("chat_node")
        builder.add_conditional_edges("chat_node", tools_condition)
        builder.add_conditional_edges("chat_node", self._should_summarize)
        builder.add_edge("summarize_node", END)
        builder.add_edge("tools", "chat_node")
        builder.set_finish_point("chat_node")

        if settings.agent.is_in_memory:
            checkpointer = InMemorySaver()
            store = InMemoryStore()
        else:
            checkpointer = await get_shared_checkpointer()
            store = await get_shared_store()

        return builder.compile(checkpointer=checkpointer, store=store)


_agent: CompiledStateGraph | None = None
_agent_lock = asyncio.Lock()


async def get_shared_agent() -> CompiledStateGraph:
    """Compile the graph once per process; tools arrive per request via config."""
    global _agent
    if _agent is None:
        async with _agent_lock:
            if _agent is None:
                _agent = await WorkspaceAgent().build_graph()
                logger.info("Workspace agent graph compiled")
    return _agent
