from functools import lru_cache

from langchain_core.callbacks import BaseCallbackHandler
from langfuse.langchain import CallbackHandler

from backend.core import settings


@lru_cache(maxsize=1)
def get_langfuse_handler() -> BaseCallbackHandler:
    return CallbackHandler(public_key=settings.langfuse.public_key)
