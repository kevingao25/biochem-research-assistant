from pydantic import BaseModel, Field


class RAGResponse(BaseModel):
    """Structured output schema for Ollama RAG responses."""

    answer: str = Field(description="Answer based strictly on the provided paper excerpts")
    sources: list[str] = Field(default_factory=list, description="arXiv PDF URLs used in the answer")
    confidence: str | None = Field(None, description="high, medium, or low")
    citations: list[str] | None = Field(None, description="arXiv IDs referenced in the answer")
