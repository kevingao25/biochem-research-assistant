from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import Settings
from src.services.agents.agentic_rag import AgenticRAGService


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def qdrant():
    client = MagicMock()
    client.search_hybrid.return_value = [
        {
            "arxiv_id": "2401.00001",
            "chunk_text": "CRISPR systems defend bacteria from phages.",
            "title": "Phage defense",
            "score": 0.9,
        }
    ]
    client.search.return_value = client.search_hybrid.return_value
    return client


@pytest.fixture
def jina():
    client = AsyncMock()
    client.embed_query.return_value = [0.1] * 10
    return client


@pytest.fixture
def ollama():
    client = AsyncMock()
    client.generate.side_effect = [
        {"response": '{"allowed": true, "reason": "biochemistry question"}'},
        {"response": '{"relevant": true, "reason": "chunks discuss the question"}'},
    ]
    client.generate_rag_answer.return_value = {
        "answer": "CRISPR systems defend bacteria from phages.",
        "sources": ["https://arxiv.org/pdf/2401.00001.pdf"],
    }
    return client


class TestAgenticRAGService:
    async def test_happy_path_retrieves_grades_and_generates(self, qdrant, jina, ollama, settings):
        service = AgenticRAGService(qdrant=qdrant, jina=jina, ollama=ollama, settings=settings)

        result = await service.ask(
            query="How does CRISPR defend bacteria from phages?",
            top_k=3,
            model="llama3.2:1b",
            use_hybrid=True,
            categories=["q-bio.BM"],
        )

        assert result["answer"] == "CRISPR systems defend bacteria from phages."
        assert result["retrieval_attempts"] == 1
        assert result["search_mode"] == "hybrid"
        assert result["sources"] == ["https://arxiv.org/pdf/2401.00001.pdf"]
        assert any("Generated" in step for step in result["reasoning_steps"])

    async def test_out_of_scope_query_stops_before_retrieval(self, qdrant, jina, ollama, settings):
        ollama.generate.return_value = {"response": '{"allowed": false, "reason": "not biology"}'}
        ollama.generate.side_effect = None
        service = AgenticRAGService(qdrant=qdrant, jina=jina, ollama=ollama, settings=settings)

        result = await service.ask(
            query="What is the capital of France?",
            top_k=3,
            model="llama3.2:1b",
            use_hybrid=True,
        )

        assert result["search_mode"] == "none"
        assert result["retrieval_attempts"] == 0
        qdrant.search_hybrid.assert_not_called()

    async def test_rewrites_query_after_empty_retrieval(self, qdrant, jina, ollama, settings):
        qdrant.search_hybrid.side_effect = [
            [],
            [{"arxiv_id": "2401.00002", "chunk_text": "Anti-phage systems block infection.", "score": 0.8}],
        ]
        ollama.generate.side_effect = [
            {"response": '{"allowed": true, "reason": "phage biology"}'},
            {"response": '{"query": "anti-phage bacterial defense systems", "reason": "more specific"}'},
            {"response": '{"relevant": true, "reason": "relevant after rewrite"}'},
        ]
        ollama.generate_rag_answer.return_value = {"answer": "Anti-phage systems block infection.", "sources": []}
        service = AgenticRAGService(qdrant=qdrant, jina=jina, ollama=ollama, settings=settings)

        result = await service.ask(
            query="Tell me about defense",
            top_k=3,
            model="llama3.2:1b",
            use_hybrid=True,
        )

        assert result["retrieval_attempts"] == 2
        assert result["rewritten_query"] == "anti-phage bacterial defense systems"
        assert result["answer"] == "Anti-phage systems block infection."
