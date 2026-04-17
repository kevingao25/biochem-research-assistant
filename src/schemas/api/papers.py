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


# A single result from a Qdrant search — includes a relevance score.
# published_date is a string here because Qdrant stores it as an ISO string in the payload.
class SearchHit(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published_date: str
    pdf_url: str
    score: float  # BM25 relevance score — higher means more relevant


# Returned by GET /papers/search?q=...
class SearchResponse(BaseModel):
    query: str
    total: int
    hits: List[SearchHit]
