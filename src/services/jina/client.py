import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"
DIMENSIONS = 1024
BATCH_SIZE = 100   # Jina recommends batching; free tier handles 100 texts per call


class JinaClient:
    """Async client for the Jina AI embeddings API.

    Uses jina-embeddings-v3 with 1024 dimensions.
    Passages and queries use different task types so the model optimizes
    each side of the retrieval pair independently.
    """

    def __init__(self, api_key: str):
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _embed(self, texts: List[str], task: str) -> List[List[float]]:
        """Call the Jina API and return a list of embedding vectors."""
        embeddings: List[List[float]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i : i + BATCH_SIZE]
                response = await client.post(
                    JINA_API_URL,
                    headers=self._headers,
                    json={
                        "model": JINA_MODEL,
                        "task": task,
                        "dimensions": DIMENSIONS,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                data = response.json()["data"]
                embeddings.extend(item["embedding"] for item in data)

        return embeddings

    async def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed text passages for indexing into Qdrant."""
        logger.info(f"Embedding {len(texts)} passages")
        return await self._embed(texts, task="retrieval.passage")

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single search query."""
        results = await self._embed([query], task="retrieval.query")
        return results[0]
