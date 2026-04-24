from src.config import get_settings
from src.services.qdrant.client import QdrantService


def make_qdrant_client() -> QdrantService:
    settings = get_settings()
    client = QdrantService(url=settings.qdrant.url)
    client.setup_collection()
    return client
