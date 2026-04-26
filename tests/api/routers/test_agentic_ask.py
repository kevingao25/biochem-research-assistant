class TestAgenticAskEndpoint:
    async def test_agentic_ask_returns_reasoning_steps(self, client, mocks):
        mocks["agentic_rag"].ask.return_value = {
            "answer": "CRISPR systems help bacteria defend against phages.",
            "sources": ["https://arxiv.org/pdf/2401.00001.pdf"],
            "chunks": [{"arxiv_id": "2401.00001", "chunk_text": "CRISPR text."}],
            "search_mode": "hybrid",
            "reasoning_steps": ["Guardrail passed.", "Retrieved chunks.", "Generated answer."],
            "retrieval_attempts": 1,
            "rewritten_query": None,
        }

        response = await client.post("/api/v1/ask-agentic", json={"query": "How does CRISPR defend bacteria?"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"].startswith("CRISPR systems")
        assert data["reasoning_steps"] == ["Guardrail passed.", "Retrieved chunks.", "Generated answer."]
        assert data["retrieval_attempts"] == 1

    async def test_agentic_ask_passes_request_options_to_service(self, client, mocks):
        mocks["agentic_rag"].ask.return_value = {
            "answer": "Answer.",
            "sources": [],
            "chunks": [],
            "search_mode": "bm25",
            "reasoning_steps": [],
            "retrieval_attempts": 0,
            "rewritten_query": None,
        }

        await client.post(
            "/api/v1/ask-agentic",
            json={
                "query": "phage defense",
                "top_k": 3,
                "model": "llama3.2:1b",
                "use_hybrid": False,
                "categories": ["q-bio.BM"],
            },
        )

        mocks["agentic_rag"].ask.assert_awaited_once_with(
            query="phage defense",
            top_k=3,
            model="llama3.2:1b",
            use_hybrid=False,
            categories=["q-bio.BM"],
        )

    async def test_agentic_ask_empty_query_is_422(self, client, mocks):
        response = await client.post("/api/v1/ask-agentic", json={"query": ""})

        assert response.status_code == 422
