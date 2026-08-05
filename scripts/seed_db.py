import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

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


def seed_initial_docs():
    if sync_client.collection_exists(settings.db.qdrant.collection_name):
        info = sync_client.get_collection(settings.db.qdrant.collection_name)
        if info.points_count > 0:
            print(
                f"Collection '{settings.db.qdrant.collection_name}' already has {info.points_count} docs, skip seeding..."
            )
            return

    if not sync_client.collection_exists(settings.db.qdrant.collection_name):
        sync_client.create_collection(
            collection_name=settings.db.qdrant.collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )

    if not os.path.exists("./.data/docs"):
        print("Folder not found")
        return

    loader = DirectoryLoader("./.data/docs", glob="**/*.pdf", loader_cls=PyPDFLoader)
    raw_docs = loader.load()

    if not raw_docs:
        print("No PDF files in folder")
        return

    # imported lazily, cuz it must happen after create_collection() above, not at module import time
    from backend.agent.utils.ingestion import chunk_documents

    chunks = chunk_documents(
        raw_docs,
        owner_id=None,
        filename=None,
        source_type="knowledge_base",
        document_id=None,
    )

    vector_store = QdrantVectorStore(
        client=sync_client,
        collection_name=settings.db.qdrant.collection_name,
        embedding=embeddings,
    )
    vector_store.add_documents(chunks)
    print("Successfully filled DB with files!")


if __name__ == "__main__":
    seed_initial_docs()
