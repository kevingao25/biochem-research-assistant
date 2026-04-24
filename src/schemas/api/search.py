
from pydantic import BaseModel, ConfigDict, Field


class HybridSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    size: int = Field(10, ge=1, le=100)
    from_: int = Field(0, ge=0, alias="from")
    categories: list[str] | None = Field(None)
    latest_papers: bool = Field(False)
    use_hybrid: bool = Field(True)
    min_score: float = Field(0.0, ge=0.0)


class SearchHit(BaseModel):
    arxiv_id: str
    title: str
    authors: str | None = None
    abstract: str | None = None
    published_date: str | None = None
    pdf_url: str | None = None
    score: float
    chunk_text: str | None = Field(None)
    section_title: str | None = Field(None)


class SearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    total: int
    hits: list[SearchHit]
    size: int
    from_: int = Field(alias="from")
    search_mode: str | None = None
