from collections.abc import Callable

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from backend.agent.utils.rag import async_client
from backend.core import settings

LoaderFn = Callable[[str], list[Document]]

_LOADER_REGISTRY: dict[str, LoaderFn] = {}


def register_loader(*extensions: str) -> Callable[[LoaderFn], LoaderFn]:
    def decorator(fn: LoaderFn) -> LoaderFn:
        for ext in extensions:
            _LOADER_REGISTRY[ext.lower()] = fn
        return fn

    return decorator


@register_loader(".pdf")
def load_pdf(path: str) -> list[Document]:
    return PyPDFLoader(path).load()


def get_loader(extension: str) -> LoaderFn:
    try:
        return _LOADER_REGISTRY[extension.lower()]
    except KeyError:
        raise ValueError(f"Unsupported file type: {extension}")


def supported_extensions() -> set[str]:
    return set(_LOADER_REGISTRY)


def chunk_documents(
    docs: list[Document],
    *,
    owner_id: str | None,
    filename: str | None,
    source_type: str,
    document_id: str | None,
) -> list[Document]:
    chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(docs)
    for chunk in chunks:
        chunk.metadata.update(
            owner_id=owner_id,
            filename=filename,
            source_type=source_type,
            document_id=document_id,
        )
    return chunks


async def delete_owner_documents(owner_id: str) -> None:
    await async_client.delete(
        collection_name=settings.db.qdrant.collection_name,
        points_selector=Filter(
            must=[FieldCondition(key="metadata.owner_id", match=MatchValue(value=owner_id))]
        ),
    )
