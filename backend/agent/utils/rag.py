from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from backend.core import settings

embeddings = FastEmbedEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

sync_client = QdrantClient(
    url=settings.db.qdrant.url,
    api_key=settings.db.qdrant.key,
)


async def init_collection_if_not_exists():
    collections = [col.name for col in sync_client.get_collections().collections]

    if settings.db.qdrant.collection_name not in collections:
        # Size 384 for fastembed
        sync_client.create_collection(
            collection_name=settings.db.qdrant.collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


async def initial_documents_load():
    pass


vector_store = QdrantVectorStore(
    client=sync_client,
    collection_name=settings.db.qdrant.collection_name,
    embedding=embeddings,
)


@lru_cache(maxsize=1)
def _get_retriever():
    return vector_store.as_retriever(search_kwargs={"k": 3})
