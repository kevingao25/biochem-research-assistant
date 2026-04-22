import pytest

from src.routers.ask import _build_user_message, _extract_sources


# ── Prompt construction ────────────────────────────────────────────────────────

class TestBuildUserMessage:
    def test_includes_all_chunks(self):
        chunks = [
            {"arxiv_id": "2401.00001", "chunk_text": "CRISPR text here."},
            {"arxiv_id": "2401.00002", "chunk_text": "Phage text here."},
        ]
        msg = _build_user_message("What is CRISPR?", chunks)
        assert "CRISPR text here." in msg
        assert "Phage text here." in msg

    def test_chunks_are_numbered(self):
        chunks = [
            {"arxiv_id": "2401.00001", "chunk_text": "First chunk."},
            {"arxiv_id": "2401.00002", "chunk_text": "Second chunk."},
        ]
        msg = _build_user_message("question", chunks)
        assert "[1. arXiv:2401.00001]" in msg
        assert "[2. arXiv:2401.00002]" in msg

    def test_query_is_included(self):
        chunks = [{"arxiv_id": "2401.00001", "chunk_text": "some text"}]
        msg = _build_user_message("How do phages evade CRISPR?", chunks)
        assert "How do phages evade CRISPR?" in msg

    def test_empty_chunks_still_includes_question(self):
        msg = _build_user_message("What is CRISPR?", [])
        assert "What is CRISPR?" in msg


# ── Source URL extraction ──────────────────────────────────────────────────────

class TestExtractSources:
    def test_arxiv_id_converted_to_pdf_url(self):
        chunks = [{"arxiv_id": "2401.00001"}]
        sources = _extract_sources(chunks)
        assert sources == ["https://arxiv.org/pdf/2401.00001.pdf"]

    def test_version_suffix_stripped(self):
        # arXiv IDs often include version like "2401.00001v2"
        chunks = [{"arxiv_id": "2401.00001v2"}]
        sources = _extract_sources(chunks)
        assert sources == ["https://arxiv.org/pdf/2401.00001.pdf"]

    def test_duplicate_papers_deduplicated(self):
        # Two chunks from the same paper → one source URL
        chunks = [
            {"arxiv_id": "2401.00001", "chunk_text": "chunk 1"},
            {"arxiv_id": "2401.00001", "chunk_text": "chunk 2"},
        ]
        sources = _extract_sources(chunks)
        assert len(sources) == 1

    def test_multiple_papers_all_included(self):
        chunks = [
            {"arxiv_id": "2401.00001"},
            {"arxiv_id": "2401.00002"},
            {"arxiv_id": "2401.00003"},
        ]
        sources = _extract_sources(chunks)
        assert len(sources) == 3

    def test_missing_arxiv_id_skipped(self):
        chunks = [{"arxiv_id": ""}, {"arxiv_id": "2401.00001"}]
        sources = _extract_sources(chunks)
        assert len(sources) == 1

    def test_empty_chunks_returns_empty_list(self):
        assert _extract_sources([]) == []
