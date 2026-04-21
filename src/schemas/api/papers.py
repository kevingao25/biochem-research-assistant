from datetime import datetime
from typing import List

from pydantic import BaseModel


# Returned by GET /papers and GET /papers/{arxiv_id}.
# Built directly from a SQLAlchemy Paper ORM object (from_attributes = True).
class PaperResponse(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published_date: datetime
    pdf_url: str

    class Config:
        from_attributes = True  # lets Pydantic read fields from ORM objects, not just dicts


# A single chunk result from a Qdrant BM25 search — includes a relevance score.
# chunk_text is the specific passage that matched the query.
# section_title indicates which part of the paper the chunk came from (None for raw-text fallback chunks).
class SearchHit(BaseModel):
    arxiv_id: str
    paper_id: str
    chunk_index: int
    chunk_text: str
    section_title: str | None
    score: float  # BM25 relevance score — higher means more relevant


# Returned by GET /papers/search?q=...
class SearchResponse(BaseModel):
    query: str
    total: int
    hits: List[SearchHit]
