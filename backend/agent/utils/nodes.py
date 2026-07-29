from langchain.messages import SystemMessage

from backend.agent.utils.state import MessagesState

from .llms import openai_llm


async def chat_node(state: MessagesState) -> dict:
    # TODO: trim messages properly
    return {
        "messages": [
            await openai_llm.ainvoke(
                [
                    SystemMessage(
                        content="You are a senior software engineer specialized in backend.",
                    )
                ]
                + state["messages"],
            )
        ]
    }
