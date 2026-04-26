class TestSearchEndpoint:
    async def test_category_filter_is_passed_to_hybrid_search(self, client, mocks):
        mocks["qdrant"].health_check.return_value = True
        mocks["jina"].embed_query.return_value = [0.1] * 10
        mocks["qdrant"].search_hybrid.return_value = [
            {
                "arxiv_id": "2401.00001",
                "title": "Phage defense",
                "authors": ["A. Researcher"],
                "abstract": "Bacterial defense mechanisms.",
                "categories": ["q-bio.BM"],
                "published_date": "2026-01-01T00:00:00+00:00",
                "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
                "score": 0.9,
                "chunk_text": "CRISPR systems defend bacteria.",
                "section_title": "Introduction",
            }
        ]

        response = await client.post(
            "/api/v1/search/",
            json={
                "query": "phage defense",
                "categories": ["q-bio.BM"],
                "latest_papers": True,
                "use_hybrid": True,
            },
        )

        assert response.status_code == 200
        mocks["qdrant"].search_hybrid.assert_called_once()
        _, kwargs = mocks["qdrant"].search_hybrid.call_args
        assert kwargs["categories"] == ["q-bio.BM"]
        assert kwargs["latest"] is True

    async def test_category_filter_is_passed_to_bm25_fallback(self, client, mocks):
        mocks["qdrant"].health_check.return_value = True
        mocks["jina"].embed_query.side_effect = RuntimeError("Jina unavailable")
        mocks["qdrant"].search.return_value = []

        response = await client.post(
            "/api/v1/search/",
            json={"query": "phage defense", "categories": ["q-bio.GN"], "use_hybrid": True},
        )

        assert response.status_code == 200
        mocks["qdrant"].search.assert_called_once()
        _, kwargs = mocks["qdrant"].search.call_args
        assert kwargs["categories"] == ["q-bio.GN"]
