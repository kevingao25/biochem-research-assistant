import json

import pytest

from src.schemas.api.ask import AskResponse


# ── /ask ──────────────────────────────────────────────────────────────────────

class TestAskEndpoint:
    async def test_happy_path_returns_correct_shape(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {"arxiv_id": "2401.00001", "chunk_text": "CRISPR is a gene editing tool."},
        ]
        mocks["ollama"].generate.return_value = "CRISPR edits DNA."

        response = await client.post("/api/v1/ask", json={"query": "What is CRISPR?"})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is CRISPR?"
        assert data["answer"] == "CRISPR edits DNA."
        assert data["sources"] == ["https://arxiv.org/pdf/2401.00001.pdf"]
        assert data["chunks_used"] == 1
        assert data["search_mode"] == "hybrid"

    async def test_empty_query_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask", json={"query": ""})
        assert response.status_code == 422

    async def test_missing_query_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask", json={})
        assert response.status_code == 422

    async def test_top_k_zero_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask", json={"query": "CRISPR", "top_k": 0})
        assert response.status_code == 422

    async def test_top_k_eleven_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask", json={"query": "CRISPR", "top_k": 11})
        assert response.status_code == 422

    async def test_cache_hit_skips_search_and_llm(self, client, mocks):
        cached = AskResponse(
            query="What is CRISPR?",
            answer="Cached answer.",
            sources=["https://arxiv.org/pdf/2401.00001.pdf"],
            chunks_used=1,
            search_mode="hybrid",
        )
        mocks["cache"].get.return_value = cached

        response = await client.post("/api/v1/ask", json={"query": "What is CRISPR?"})

        assert response.status_code == 200
        assert response.json()["answer"] == "Cached answer."
        mocks["qdrant"].search_hybrid.assert_not_called()
        mocks["ollama"].generate.assert_not_called()

    async def test_zero_chunks_returns_graceful_message(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = []

        response = await client.post("/api/v1/ask", json={"query": "What is CRISPR?"})

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_used"] == 0
        assert "find" in data["answer"].lower()
        mocks["ollama"].generate.assert_not_called()

    async def test_answer_is_cached_after_generation(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {"arxiv_id": "2401.00001", "chunk_text": "Some text."},
        ]
        mocks["ollama"].generate.return_value = "An answer."

        await client.post("/api/v1/ask", json={"query": "What is CRISPR?"})

        mocks["cache"].set.assert_called_once()


# ── /ask/stream ───────────────────────────────────────────────────────────────

class TestAskStreamEndpoint:
    async def test_response_is_event_stream(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {"arxiv_id": "2401.00001", "chunk_text": "Some text."},
        ]

        async def mock_stream(*args, **kwargs):
            yield "Hello "
            yield "world."

        mocks["ollama"].generate_stream = mock_stream

        response = await client.post("/api/v1/ask/stream", json={"query": "What is CRISPR?"})

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    async def test_first_event_is_metadata(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {"arxiv_id": "2401.00001", "chunk_text": "Some text."},
        ]

        async def mock_stream(*args, **kwargs):
            yield "token"

        mocks["ollama"].generate_stream = mock_stream

        response = await client.post("/api/v1/ask/stream", json={"query": "What is CRISPR?"})

        # Parse first SSE event from the body
        first_event_line = next(
            line for line in response.text.splitlines() if line.startswith("data:")
        )
        first_event = json.loads(first_event_line[len("data: "):])

        assert "sources" in first_event
        assert "chunks_used" in first_event
        assert "search_mode" in first_event

    async def test_stream_ends_with_done_event(self, client, mocks):
        mocks["cache"].get.return_value = None
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {"arxiv_id": "2401.00001", "chunk_text": "Some text."},
        ]

        async def mock_stream(*args, **kwargs):
            yield "token"

        mocks["ollama"].generate_stream = mock_stream

        response = await client.post("/api/v1/ask/stream", json={"query": "What is CRISPR?"})

        last_event_line = next(
            line for line in reversed(response.text.splitlines()) if line.startswith("data:")
        )
        last_event = json.loads(last_event_line[len("data: "):])

        assert last_event == {"done": True}

    async def test_stream_empty_query_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask/stream", json={"query": ""})
        assert response.status_code == 422
