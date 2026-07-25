import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
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
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

    if not os.path.exists("./.data/docs"):
        print("Folder not found")
        return

    loader = DirectoryLoader("./.data/docs", glob="**/*.pdf", loader_cls=PyPDFLoader)
    raw_docs = loader.load()

    if not raw_docs:
        print("No PDF files in folder")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(raw_docs)

    vector_store = QdrantVectorStore(
        client=sync_client,
        collection_name=settings.db.qdrant.collection_name,
        embedding=embeddings,
    )
    vector_store.add_documents(chunks)
    print("Successfully filled DB with files!")


if __name__ == "__main__":
    seed_initial_docs()
