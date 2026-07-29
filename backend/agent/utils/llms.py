from langchain_openai import ChatOpenAI

from backend.core import settings
from .tools import tools_list

openai_llm_base = ChatOpenAI(
    model=settings.llms.openai_gpt_5_mini,
    base_url=settings.llms.openai_base_url,
    api_key=settings.llms.openai_api_key,
    temperature=0.8,
)
openai_llm = openai_llm_base.bind_tools(tools=tools_list)
