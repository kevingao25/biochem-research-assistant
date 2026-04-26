from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from src.dependencies import get_agentic_rag, get_cache, get_jina, get_langfuse, get_ollama, get_qdrant


@asynccontextmanager
async def _noop_lifespan(app):
    # Skips real startup so tests don't need Postgres, Qdrant, Redis, etc. running
    yield


@pytest.fixture
def mocks():
    """One mock per injected service. Tests set return_value as needed."""
    return {
        "qdrant": MagicMock(),  # search_hybrid / search are sync
        "jina": AsyncMock(),  # embed_query is async
        "ollama": AsyncMock(),  # generate / generate_stream are async
        "cache": AsyncMock(),  # get / set are async
        "langfuse": MagicMock(),  # trace / span are sync context managers
        "agentic_rag": AsyncMock(),  # ask is async
    }


@pytest.fixture
async def client(mocks):
    """AsyncClient wired to the FastAPI app with all services mocked out."""
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides = {
        get_qdrant: lambda: mocks["qdrant"],
        get_jina: lambda: mocks["jina"],
        get_ollama: lambda: mocks["ollama"],
        get_cache: lambda: mocks["cache"],
        get_langfuse: lambda: mocks["langfuse"],
        get_agentic_rag: lambda: mocks["agentic_rag"],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides = {}
