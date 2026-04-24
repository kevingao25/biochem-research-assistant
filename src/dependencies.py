from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.services.cache.client import CacheClient
from src.services.jina.client import JinaClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.qdrant.client import QdrantService


def get_db_session(request: Request) -> Generator[Session, None, None]:
    # Task 9 will replace this with db.get_session() once main.py stores a BaseDatabase
    session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_qdrant(request: Request) -> QdrantService:
    return request.app.state.qdrant


def get_jina(request: Request) -> JinaClient:
    return request.app.state.jina


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


def get_cache(request: Request) -> CacheClient:
    return request.app.state.cache


def get_langfuse(request: Request) -> LangfuseTracer:
    return request.app.state.langfuse


# Shorthand type aliases — routes declare these as parameter types instead
# of writing out Annotated[Session, Depends(get_db_session)] every time.
SessionDep = Annotated[Session, Depends(get_db_session)]
QdrantDep = Annotated[QdrantService, Depends(get_qdrant)]
JinaDep = Annotated[JinaClient, Depends(get_jina)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama)]
CacheDep = Annotated[CacheClient, Depends(get_cache)]
LangfuseDep = Annotated[LangfuseTracer, Depends(get_langfuse)]
