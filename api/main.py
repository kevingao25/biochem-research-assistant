import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request

from src.db.interfaces.postgresql import PostgreSQLDatabase
from src.schemas.database.config import PostgreSQLSettings
from src.routers.ask import ask_router, stream_router
from src.routers.papers import router as papers_router
from src.services.cache.client import CacheClient
from src.services.jina.client import JinaClient
from src.services.langfuse.factory import make_langfuse_tracer
from src.services.ollama.client import OllamaClient
from src.services.qdrant.client import QdrantService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    # PostgreSQL — Task 13 will store db directly; for now expose session_factory
    # so dependencies.py (Task 9) can keep working unchanged
    db = PostgreSQLDatabase(config=PostgreSQLSettings(database_url=os.environ["DATABASE_URL"]))
    db.startup()
    app.state.db = db
    app.state.session_factory = db.session_factory
    logger.info("Database ready")

    # Qdrant — create collection if it doesn't exist yet
    qdrant = QdrantService(url=os.environ["QDRANT_URL"])
    qdrant.setup_collection()
    app.state.qdrant = qdrant
    logger.info("Qdrant ready")

    # Jina AI — dense embedding client for hybrid search
    app.state.jina = JinaClient(api_key=os.environ["JINA_API_KEY"])
    logger.info("Jina client ready")

    # Ollama — local LLM for question answering
    from src.config import get_settings
    app.state.ollama = OllamaClient(get_settings())
    logger.info("Ollama client ready")

    # Redis — exact-match answer cache
    redis_client = aioredis.Redis.from_url(os.environ["REDIS_URL"])
    app.state.cache = CacheClient(redis_client)
    logger.info("Cache ready")

    # Langfuse — LLM observability (no-op if keys are not set)
    app.state.langfuse = make_langfuse_tracer()
    logger.info("Langfuse ready")

    yield

    # Teardown — flush traces and close connections cleanly
    app.state.langfuse.shutdown()
    await redis_client.aclose()
    app.state.db.teardown()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Biochem Research Assistant API",
    description="Search and query biochemistry papers for research",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(papers_router, prefix="/api/v1")
app.include_router(ask_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1/ask")


@app.get("/health")
async def health(request: Request):
    """Check liveness of each downstream service the API depends on."""
    import httpx
    from sqlalchemy import text

    db_ok = False
    try:
        with app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    qdrant_ok = app.state.qdrant.health_check()

    redis_ok = False
    try:
        await app.state.cache.redis.ping()
        redis_ok = True
    except Exception:
        pass

    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{os.environ['OLLAMA_URL']}/api/version")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    services = {
        "postgres": "ok" if db_ok else "unreachable",
        "qdrant":   "ok" if qdrant_ok else "unreachable",
        "redis":    "ok" if redis_ok else "unreachable",
        "ollama":   "ok" if ollama_ok else "unreachable",
    }
    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
