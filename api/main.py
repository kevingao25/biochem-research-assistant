import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.session import create_tables, make_engine, make_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    engine = make_engine(os.environ["DATABASE_URL"])
    app.state.session_factory = make_session_factory(engine)
    create_tables(engine)
    logger.info("Database ready")
    yield
    engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Biochem Research Assistant API",
    description="Search and query biochemistry papers for research",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}
