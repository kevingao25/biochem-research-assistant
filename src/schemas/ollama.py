from typing import List, Optional

from pydantic import BaseModel, Field


class RAGResponse(BaseModel):
    """Structured output schema for Ollama RAG responses."""

    answer: str = Field(description="Answer based strictly on the provided paper excerpts")
    sources: List[str] = Field(default_factory=list, description="arXiv PDF URLs used in the answer")
    confidence: Optional[str] = Field(None, description="high, medium, or low")
    citations: Optional[List[str]] = Field(None, description="arXiv IDs referenced in the answer")
