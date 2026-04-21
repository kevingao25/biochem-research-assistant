import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from src.db.session import create_tables, make_engine, make_session_factory
from src.routers.papers import router as papers_router
from src.services.qdrant_client import QdrantService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    # PostgreSQL
    engine = make_engine(os.environ["DATABASE_URL"])
    app.state.session_factory = make_session_factory(engine)
    create_tables(engine)
    logger.info("Database ready")

    # Qdrant — create collection if it doesn't exist yet
    qdrant = QdrantService(url=os.environ["QDRANT_URL"])
    qdrant.setup_collection()
    app.state.qdrant = qdrant
    logger.info("Qdrant ready")

    yield

    engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Biochem Research Assistant API",
    description="Search and query biochemistry papers for research",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(papers_router, prefix="/api/v1")


@app.get("/health")
def health(request: Request):
    """Check liveness of each downstream service the API depends on."""
    from sqlalchemy import text

    db_ok = False
    try:
        with app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    qdrant_ok = app.state.qdrant.health_check()

    services = {
        "postgres": "ok" if db_ok else "unreachable",
        "qdrant":   "ok" if qdrant_ok else "unreachable",
    }
    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
