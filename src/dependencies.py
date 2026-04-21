from typing import Annotated, Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.db.session import get_session
from src.services.jina_client import JinaClient
from src.services.qdrant_client import QdrantService


def get_db_session(request: Request) -> Generator[Session, None, None]:
    with get_session(request.app.state.session_factory) as session:
        yield session


def get_qdrant(request: Request) -> QdrantService:
    return request.app.state.qdrant


def get_jina(request: Request) -> JinaClient:
    return request.app.state.jina


# Shorthand type aliases — routes declare these as parameter types instead
# of writing out Annotated[Session, Depends(get_db_session)] every time.
SessionDep = Annotated[Session, Depends(get_db_session)]
QdrantDep = Annotated[QdrantService, Depends(get_qdrant)]
JinaDep = Annotated[JinaClient, Depends(get_jina)]
