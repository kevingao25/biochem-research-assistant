
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Question to answer")
    top_k: int = Field(5, ge=1, le=10, description="Number of paper chunks to retrieve")
    model: str = Field("llama3.2:1b", description="Ollama model to use")
    use_hybrid: bool = Field(
        True, description="Use hybrid search (BM25 + dense); falls back to BM25 if Jina is unreachable"
    )
    categories: list[str] | None = Field(
        None, description="Filter by arXiv categories (e.g. ['q-bio.BM', 'q-bio.GN']); not yet implemented in search"
    )


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[str]  # arXiv PDF URLs of papers the answer draws from
    chunks_used: int  # how many chunks were passed to the LLM
    search_mode: str  # "hybrid" or "bm25"
