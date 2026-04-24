from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HybridSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    size: int = Field(10, ge=1, le=100)
    from_: int = Field(0, ge=0, alias="from")
    categories: Optional[List[str]] = Field(None)
    latest_papers: bool = Field(False)
    use_hybrid: bool = Field(True)
    min_score: float = Field(0.0, ge=0.0)


class SearchHit(BaseModel):
    arxiv_id: str
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    published_date: Optional[str] = None
    pdf_url: Optional[str] = None
    score: float
    chunk_text: Optional[str] = Field(None)
    section_title: Optional[str] = Field(None)


class SearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    total: int
    hits: List[SearchHit]
    size: int
    from_: int = Field(alias="from")
    search_mode: Optional[str] = None
