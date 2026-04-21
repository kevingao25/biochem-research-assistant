import logging
from typing import List, Optional

from src.schemas.indexing.models import ChunkMetadata, TextChunk
from src.schemas.pdf_parser.models import PaperSection

logger = logging.getLogger(__name__)

CHUNK_SIZE = 600      # target words per chunk (sliding window)
OVERLAP = 100         # words shared between adjacent chunks
MIN_CHUNK = 100       # discard chunks smaller than this
MAX_SECTION = 900     # sections larger than this get split; smaller ones stay whole


class TextChunker:
    """Splits paper text into overlapping word-based chunks.

    Prefers section boundaries when available so each chunk stays
    within a single semantic unit (Introduction, Methods, etc.).
    Falls back to plain sliding-window chunking when sections are absent.
    """

    def chunk_paper(
        self,
        title: str,
        abstract: str,
        arxiv_id: str,
        paper_id: str,
        sections: Optional[List[PaperSection]] = None,
        raw_text: Optional[str] = None,
    ) -> List[TextChunk]:
        """Main entry point. Tries section-based chunking first, falls back to raw text.

        Every chunk gets a header (title + abstract) prepended so search results
        already contain the paper's context without a second database lookup.
        """
        header = f"{title}\n\nAbstract: {abstract}"

        if sections:
            chunks = self._chunk_by_sections(header, sections, arxiv_id, paper_id)
            if chunks:
                return chunks
            logger.warning(f"Section-based chunking produced no chunks for {arxiv_id}, falling back")

        if raw_text:
            return self._chunk_text(raw_text, arxiv_id, paper_id)

        logger.warning(f"No text available to chunk for {arxiv_id}")
        return []

    def _chunk_by_sections(
        self,
        header: str,
        sections: List[PaperSection],
        arxiv_id: str,
        paper_id: str,
    ) -> List[TextChunk]:
        """Chunk using document structure. Three cases per section:

        - Too small (<100 words): hold in a pending buffer and combine with
          neighboring small sections so we don't produce tiny useless chunks.
        - Just right (100–900 words): one section = one chunk.
        - Too large (>900 words): split with a sliding window, keeping the
          section title on each sub-chunk so we know where it came from.
        """
        chunks: List[TextChunk] = []
        pending: List[PaperSection] = []   # small sections waiting to be combined

        for i, section in enumerate(sections):
            words = section.content.split()
            is_last = i == len(sections) - 1

            if len(words) < MIN_CHUNK:
                pending.append(section)
                # Flush pending when we hit a large section or the end
                if is_last or len(sections[i + 1].content.split()) >= MIN_CHUNK:
                    if pending:
                        chunks.extend(self._flush_pending(header, pending, len(chunks), arxiv_id, paper_id))
                        pending = []
            elif len(words) <= MAX_SECTION:
                # Section fits in one chunk
                text = f"{header}\n\nSection: {section.title}\n\n{section.content}"
                chunks.append(self._make_chunk(text, section.title, len(chunks), arxiv_id, paper_id))
            else:
                # Section too large — split it with sliding window
                section_text = f"Section: {section.title}\n\n{section.content}"
                for sub in self._sliding_window(section_text, arxiv_id, paper_id, base_index=len(chunks)):
                    sub.metadata.section_title = section.title
                    chunks.append(sub)

        return chunks

    def _flush_pending(
        self,
        header: str,
        sections: List[PaperSection],
        base_index: int,
        arxiv_id: str,
        paper_id: str,
    ) -> List[TextChunk]:
        """Merge accumulated small sections into a single chunk.

        Small sections (e.g. Acknowledgements, Data Availability) are too short
        to be useful on their own. Grouping them avoids polluting the index with
        near-empty chunks that would score poorly in search.
        """
        combined = "\n\n".join(f"Section: {s.title}\n\n{s.content}" for s in sections)
        text = f"{header}\n\n{combined}"
        title = " + ".join(s.title for s in sections[:3])
        return [self._make_chunk(text, title, base_index, arxiv_id, paper_id)]

    def _chunk_text(self, text: str, arxiv_id: str, paper_id: str) -> List[TextChunk]:
        """Fallback: chunk raw text with no section awareness."""
        return self._sliding_window(text, arxiv_id, paper_id, base_index=0)

    def _sliding_window(self, text: str, arxiv_id: str, paper_id: str, base_index: int) -> List[TextChunk]:
        """Split text into overlapping windows of CHUNK_SIZE words.

        Each window advances by (CHUNK_SIZE - OVERLAP) words, so consecutive
        chunks share OVERLAP words. The overlap ensures that a sentence spanning
        a chunk boundary appears in full in at least one chunk, preventing
        information loss at the edges.
        """
        words = text.split()
        chunks: List[TextChunk] = []
        pos = 0
        idx = base_index

        while pos < len(words):
            end = min(pos + CHUNK_SIZE, len(words))
            chunk_words = words[pos:end]

            if len(chunk_words) >= MIN_CHUNK:
                chunk_text = " ".join(chunk_words)
                chunks.append(self._make_chunk(chunk_text, None, idx, arxiv_id, paper_id))
                idx += 1

            if end >= len(words):
                break
            pos += CHUNK_SIZE - OVERLAP

        return chunks

    def _make_chunk(
        self,
        text: str,
        section_title: Optional[str],
        index: int,
        arxiv_id: str,
        paper_id: str,
    ) -> TextChunk:
        """Wrap text and metadata into a TextChunk ready for indexing."""
        return TextChunk(
            text=text,
            metadata=ChunkMetadata(
                chunk_index=index,
                word_count=len(text.split()),
                section_title=section_title,
            ),
            arxiv_id=arxiv_id,
            paper_id=paper_id,
        )
