import pytest

from src.schemas.pdf_parser.models import PaperSection
from src.services.chunker import MIN_CHUNK, TextChunker


@pytest.fixture
def chunker():
    return TextChunker()


# ── Noise section filtering ────────────────────────────────────────────────────


class TestIsNoiseSection:
    def test_known_noise_sections_are_filtered(self, chunker):
        for title in ["References", "Bibliography", "Acknowledgements", "Funding"]:
            assert chunker._is_noise_section(title)

    def test_case_insensitive(self, chunker):
        assert chunker._is_noise_section("REFERENCES")
        assert chunker._is_noise_section("references")

    def test_whitespace_stripped(self, chunker):
        assert chunker._is_noise_section("  References  ")

    def test_content_sections_not_filtered(self, chunker):
        for title in ["Introduction", "Methods", "Results", "Discussion"]:
            assert not chunker._is_noise_section(title)


# ── Duplicate abstract detection ───────────────────────────────────────────────


class TestIsDuplicateAbstract:
    def test_high_overlap_is_duplicate(self, chunker):
        abstract_words = set("the quick brown fox jumps over the lazy dog".split())
        # 9 of 10 unique words overlap → >80%
        content = "the quick brown fox jumps over the lazy dog extra"
        assert chunker._is_duplicate_abstract(content, abstract_words)

    def test_low_overlap_is_not_duplicate(self, chunker):
        abstract_words = set("protein structure folding mechanism".split())
        content = "bacteriophage CRISPR defense systems in bacteria"
        assert not chunker._is_duplicate_abstract(content, abstract_words)

    def test_empty_content_is_not_duplicate(self, chunker):
        abstract_words = set("some words here".split())
        assert not chunker._is_duplicate_abstract("", abstract_words)


# ── Section-based chunking ─────────────────────────────────────────────────────


class TestChunkBySections:
    def test_normal_section_produces_one_chunk(self, chunker):
        sections = [PaperSection(title="Introduction", content=" ".join(["word"] * 300))]
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1", sections=sections)
        assert len(chunks) == 1
        assert chunks[0].metadata.section_title == "Introduction"

    def test_noise_section_is_skipped(self, chunker):
        sections = [
            PaperSection(title="Introduction", content=" ".join(["word"] * 300)),
            PaperSection(title="References", content=" ".join(["ref"] * 300)),
        ]
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1", sections=sections)
        assert len(chunks) == 1
        assert all(c.metadata.section_title != "References" for c in chunks)

    def test_large_section_is_split(self, chunker):
        # 1000 words > MAX_SECTION (900) → split into multiple chunks
        sections = [PaperSection(title="Methods", content=" ".join(["word"] * 1000))]
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1", sections=sections)
        assert len(chunks) > 1

    def test_tiny_sections_are_merged(self, chunker):
        # Two tiny sections (< MIN_CHUNK each) → merged into one chunk
        sections = [
            PaperSection(title="Note", content=" ".join(["word"] * 50)),
            PaperSection(title="Remark", content=" ".join(["word"] * 50)),
        ]
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1", sections=sections)
        assert len(chunks) == 1

    def test_falls_back_to_raw_text_when_no_sections(self, chunker):
        raw = " ".join(["word"] * 300)
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1", raw_text=raw)
        assert len(chunks) >= 1
        assert all(c.metadata.section_title is None for c in chunks)

    def test_returns_empty_when_no_text(self, chunker):
        chunks = chunker.chunk_paper("Title", "Abstract", "arxiv:1", "paper-1")
        assert chunks == []


# ── Sliding window ─────────────────────────────────────────────────────────────


class TestSlidingWindow:
    def test_short_text_produces_one_chunk(self, chunker):
        text = " ".join(["word"] * 200)
        chunks = chunker._sliding_window(text, "arxiv:1", "paper-1", base_index=0)
        assert len(chunks) == 1

    def test_long_text_produces_multiple_chunks(self, chunker):
        text = " ".join(["word"] * 1500)
        chunks = chunker._sliding_window(text, "arxiv:1", "paper-1", base_index=0)
        assert len(chunks) > 1

    def test_text_below_min_size_produces_no_chunks(self, chunker):
        text = " ".join(["word"] * (MIN_CHUNK - 1))
        chunks = chunker._sliding_window(text, "arxiv:1", "paper-1", base_index=0)
        assert len(chunks) == 0

    def test_chunk_indices_start_at_base_index(self, chunker):
        text = " ".join(["word"] * 1500)
        chunks = chunker._sliding_window(text, "arxiv:1", "paper-1", base_index=5)
        assert chunks[0].metadata.chunk_index == 5
        assert chunks[-1].metadata.chunk_index == 5 + len(chunks) - 1
