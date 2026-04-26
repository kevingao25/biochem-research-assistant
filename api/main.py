import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import get_settings
from src.db.factory import make_database
from src.routers.agentic_ask import router as agentic_ask_router
from src.routers.ask import ask_router, stream_router
from src.routers.health import router as health_router
from src.routers.papers import router as papers_router
from src.routers.search import router as search_router
from src.services.agents.factory import make_agentic_rag_service
from src.services.arxiv.factory import make_arxiv_client
from src.services.cache.factory import make_cache_client
from src.services.jina.factory import make_jina_client
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.factory import make_ollama_client
from src.services.qdrant.factory import make_qdrant_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    # Everything before `yield` runs at startup; everything after runs at shutdown.
    # FastAPI calls this once and keeps the app alive between the two sections.
    logger.info("Starting Biochem Research Assistant API...")

    settings = get_settings()
    app.state.settings = settings

    app.state.database = make_database()
    logger.info("Database ready")

    app.state.qdrant = make_qdrant_client()
    logger.info("Qdrant ready")

    app.state.jina = make_jina_client()
    logger.info("Jina client ready")

    app.state.ollama = make_ollama_client()
    logger.info("Ollama client ready")

    app.state.cache = make_cache_client(settings)
    logger.info("Cache ready")

    app.state.langfuse = make_langfuse_tracer()
    logger.info("Langfuse ready")

    app.state.arxiv = make_arxiv_client()
    logger.info("ArXiv client ready")

    app.state.agentic_rag = make_agentic_rag_service(
        qdrant=app.state.qdrant,
        jina=app.state.jina,
        ollama=app.state.ollama,
        settings=settings,
    )
    logger.info("Agentic RAG ready")

    logger.info("API ready")
    yield

    app.state.langfuse.shutdown()
    app.state.database.teardown()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Biochem Research Assistant API",
    description="Search and query biochemistry papers for research",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(papers_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1/ask")
app.include_router(agentic_ask_router, prefix="/api/v1")
