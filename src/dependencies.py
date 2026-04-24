from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config import Settings
from src.db.interfaces.base import BaseDatabase
from src.services.cache.client import CacheClient
from src.services.jina.client import JinaClient
from src.services.langfuse.client import LangfuseTracer
from src.services.ollama.client import OllamaClient
from src.services.qdrant.client import QdrantService

if TYPE_CHECKING:
    # docling is an optional heavy dependency; only imported for type checking
    from src.services.pdf_parser.parser import PDFProcessor


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> BaseDatabase:
    return request.app.state.database


def get_db_session(database: Annotated[BaseDatabase, Depends(get_database)]) -> Generator[Session, None, None]:
    with database.get_session() as session:
        yield session


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


def get_arxiv(request: Request) -> Callable:
    # app.state.arxiv holds the fetch_papers function directly
    return request.app.state.arxiv


def get_pdf_parser(request: Request) -> "PDFProcessor":
    return request.app.state.pdf_parser


# Shorthand type aliases for route parameters
SettingsDep = Annotated[Settings, Depends(get_request_settings)]
DatabaseDep = Annotated[BaseDatabase, Depends(get_database)]
SessionDep = Annotated[Session, Depends(get_db_session)]
QdrantDep = Annotated[QdrantService, Depends(get_qdrant)]
JinaDep = Annotated[JinaClient, Depends(get_jina)]
OllamaDep = Annotated[OllamaClient, Depends(get_ollama)]
CacheDep = Annotated[CacheClient, Depends(get_cache)]
LangfuseDep = Annotated[LangfuseTracer, Depends(get_langfuse)]
ArxivDep = Annotated[Callable, Depends(get_arxiv)]
# PDFParserDep omitted — docling not installed in dev; add when available
