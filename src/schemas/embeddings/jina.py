from pydantic import BaseModel, Field


class JinaEmbeddingConfig(BaseModel):
    """Configuration for Jina AI embedding requests."""

    model: str = Field(default="jina-embeddings-v3")
    dimensions: int = Field(default=1024)
    task: str = Field(default="retrieval.query")
    late_chunking: bool = Field(default=False)
