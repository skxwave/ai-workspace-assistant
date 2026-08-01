from langchain.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.core import settings
from .prompts import system_prompt_template


def _openai_llm(
    model: str,
    temperature: float = 0.8,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.llms.openai_base_url,
        api_key=settings.llms.openai_api_key,
        temperature=temperature,
    )


openai_llm = _openai_llm(settings.llms.openai_gpt_5_mini)
summarize_llm = _openai_llm(settings.llms.openai_gpt_5_mini)


def build_llm_chain(
    llm: BaseChatModel,
    tools: list | None = None,
    prompt_template: ChatPromptTemplate = system_prompt_template,
) -> Runnable:
    if tools:
        llm = llm.bind_tools(tools=tools)
    if prompt_template:
        return prompt_template | llm
    return llm
