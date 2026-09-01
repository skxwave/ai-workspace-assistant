from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, VectorParams

from backend.core import settings

embeddings = OpenAIEmbeddings(
    model=settings.llms.openai_embedding_model,
    base_url=settings.llms.openai_base_url,
    api_key=settings.llms.openai_api_key,
)

sync_client = QdrantClient(
    url=settings.db.qdrant.url,
    api_key=settings.db.qdrant.key,
)
async_client = AsyncQdrantClient(
    url=settings.db.qdrant.url,
    api_key=settings.db.qdrant.key,
)


async def init_collection_if_not_exists():
    collections = [col.name for col in sync_client.get_collections().collections]

    if settings.db.qdrant.collection_name not in collections:
        # Size 1536 for OpenAI text-embedding-3-small
        sync_client.create_collection(
            collection_name=settings.db.qdrant.collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )


vector_store = QdrantVectorStore(
    client=sync_client,
    collection_name=settings.db.qdrant.collection_name,
    embedding=embeddings,
    # pass if no collection; it will create it later (in lifespan)
    validate_collection_config=False,
)


@lru_cache(maxsize=1)
def get_retriever():
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 3,
            "filter": Filter(
                must=[
                    FieldCondition(
                        key="metadata.source_type", match=MatchValue(value="knowledge_base")
                    )
                ]
            ),
        },
    )
