import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from src.embeddings import embeddings 

load_dotenv()

COLLECTION_NAME = "spec2rtl"

VECTOR_SIZE = 1024 



def create_vector_store():

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url:
        raise ValueError("QDRANT_URL is not set in .env")

    if not api_key:
        raise ValueError("QDRANT_API_KEY is not set in .env")

    # Connect to Qdrant Cloud
    client = QdrantClient(
        url=url,
        api_key=api_key
    )

    # Check whether collection already exists
    collections = client.get_collections().collections

    existing_collections = [
        collection.name
        for collection in collections
    ]

    # Create collection if it does not exist
    if COLLECTION_NAME not in existing_collections:

        client.create_collection(
            collection_name=COLLECTION_NAME,

            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            ) )
    vector_store = QdrantVectorStore(client, COLLECTION_NAME , embedding = embeddings)
    return vector_store
