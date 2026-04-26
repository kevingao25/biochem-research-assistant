from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Question to answer")
    top_k: int = Field(5, ge=1, le=10, description="Number of paper chunks to retrieve")
    model: str = Field("llama3.2:1b", description="Ollama model to use")
    use_hybrid: bool = Field(
        True, description="Use hybrid search (BM25 + dense); falls back to BM25 if Jina is unreachable"
    )
    categories: list[str] | None = Field(
        None, description="Filter retrieval to arXiv categories (e.g. ['q-bio.BM', 'q-bio.GN'])"
    )


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[str]  # arXiv PDF URLs of papers the answer draws from
    chunks_used: int  # how many chunks were passed to the LLM
    search_mode: str  # "hybrid" or "bm25"


class AgenticAskResponse(AskResponse):
    reasoning_steps: list[str]
    retrieval_attempts: int
    rewritten_query: str | None = None
    trace_id: str | None = None


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, description="Langfuse trace id returned by /ask-agentic")
    score: float = Field(..., ge=-1.0, le=1.0, description="User feedback score from -1 to 1")
    comment: str | None = Field(None, max_length=1000, description="Optional feedback note")


class FeedbackResponse(BaseModel):
    success: bool
    message: str
