from langchain_openai import ChatOpenAI

from backend.core import settings

openai_llm = ChatOpenAI(
    model=settings.llms.openai_gpt_4o_mini,
    base_url=settings.llms.openai_base_url,
    api_key=settings.llms.openai_api_key,
    temperature=0.8,
)
