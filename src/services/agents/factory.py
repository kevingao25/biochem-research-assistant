from src.config import Settings
from src.services.agents.agentic_rag import AgenticRAGService
from src.services.jina.client import JinaClient
from src.services.ollama.client import OllamaClient
from src.services.qdrant.client import QdrantService


def make_agentic_rag_service(
    qdrant: QdrantService,
    jina: JinaClient,
    ollama: OllamaClient,
    settings: Settings,
) -> AgenticRAGService:
    return AgenticRAGService(qdrant=qdrant, jina=jina, ollama=ollama, settings=settings)
