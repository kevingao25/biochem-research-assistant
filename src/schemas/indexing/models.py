from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    chunk_index: int  # position of this chunk within the paper (0-based)
    word_count: int
    section_title: str | None = None  # None when falling back to raw-text chunking


class TextChunk(BaseModel):
    """A single indexable unit: chunk text plus enough metadata to trace it back to its paper."""

    text: str
    metadata: ChunkMetadata
    arxiv_id: str
    paper_id: str  # UUID from the papers table
