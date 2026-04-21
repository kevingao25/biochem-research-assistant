import logging
import uuid
from typing import List, Optional

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models

from src.schemas.indexing.models import TextChunk

logger = logging.getLogger(__name__)

COLLECTION = "papers_chunks"
BM25_MODEL = "Qdrant/bm25"
DENSE_DIMENSIONS = 1024


class QdrantService:
    def __init__(self, url: str):
        self.client = QdrantClient(url=url)
        self._encoder: SparseTextEmbedding | None = None

    @property
    def encoder(self) -> SparseTextEmbedding:
        # Lazy init — the model downloads on first use, so we defer until needed.
        if self._encoder is None:
            logger.info(f"Loading BM25 encoder: {BM25_MODEL}")
            self._encoder = SparseTextEmbedding(model_name=BM25_MODEL)
        return self._encoder

    def setup_collection(self) -> None:
        """Create the papers_chunks collection, or recreate it if the dense vector is missing."""
        existing = {c.name for c in self.client.get_collections().collections}

        if COLLECTION in existing:
            info = self.client.get_collection(COLLECTION)
            has_dense = "dense" in (info.config.params.vectors or {})
            if has_dense:
                logger.info(f"Qdrant collection '{COLLECTION}' already exists with dense vectors")
                return
            # Collection exists but predates dense vectors — drop and recreate.
            logger.info(f"Recreating '{COLLECTION}' to add dense vector field")
            self.client.delete_collection(COLLECTION)

        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": models.VectorParams(
                    size=DENSE_DIMENSIONS,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(),
            },
        )
        logger.info(f"Qdrant collection '{COLLECTION}' created with BM25 + dense vectors")

    def index_chunk(self, chunk: TextChunk, dense_embedding: Optional[List[float]] = None) -> None:
        """Index a single text chunk with BM25 sparse vector and optional dense embedding."""
        sparse_embedding = next(self.encoder.embed([chunk.text]))

        # Deterministic UUID from arxiv_id + chunk_index so re-indexing is idempotent.
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.arxiv_id}_{chunk.metadata.chunk_index}"))

        vector: dict = {
            "bm25": models.SparseVector(
                indices=sparse_embedding.indices.tolist(),
                values=sparse_embedding.values.tolist(),
            )
        }
        if dense_embedding is not None:
            vector["dense"] = dense_embedding

        self.client.upsert(
            collection_name=COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    payload={
                        "arxiv_id": chunk.arxiv_id,
                        "paper_id": chunk.paper_id,
                        "chunk_index": chunk.metadata.chunk_index,
                        "chunk_text": chunk.text,
                        "section_title": chunk.metadata.section_title,
                        "word_count": chunk.metadata.word_count,
                    },
                    vector=vector,
                )
            ],
        )

    def index_chunks(self, chunks: List[TextChunk], dense_embeddings: Optional[List[List[float]]] = None) -> None:
        """Batch-index a list of chunks for one paper."""
        for i, chunk in enumerate(chunks):
            embedding = dense_embeddings[i] if dense_embeddings else None
            self.index_chunk(chunk, dense_embedding=embedding)
        logger.info(f"Indexed {len(chunks)} chunks for {chunks[0].arxiv_id if chunks else '?'}")

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """BM25 keyword search over chunk text."""
        query_embedding = next(self.encoder.query_embed(query))
        results = self.client.query_points(
            collection_name=COLLECTION,
            query=models.SparseVector(
                indices=query_embedding.indices.tolist(),
                values=query_embedding.values.tolist(),
            ),
            using="bm25",
            limit=limit,
        )
        return self._format(results.points)

    def search_hybrid(self, query: str, dense_embedding: List[float], limit: int = 10) -> List[dict]:
        """Hybrid BM25 + dense search using Qdrant's native RRF fusion.

        Qdrant fetches the top 20 from each index independently (prefetch),
        then merges them with Reciprocal Rank Fusion before returning `limit` results.
        """
        query_sparse = next(self.encoder.query_embed(query))

        results = self.client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                models.Prefetch(
                    query=models.SparseVector(
                        indices=query_sparse.indices.tolist(),
                        values=query_sparse.values.tolist(),
                    ),
                    using="bm25",
                    limit=20,
                ),
                models.Prefetch(
                    query=dense_embedding,
                    using="dense",
                    limit=20,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        )
        return self._format(results.points)

    def _format(self, points) -> List[dict]:
        return [
            {
                "arxiv_id": point.payload["arxiv_id"],
                "paper_id": point.payload["paper_id"],
                "chunk_index": point.payload["chunk_index"],
                "chunk_text": point.payload["chunk_text"],
                "section_title": point.payload.get("section_title"),
                "score": point.score,
            }
            for point in points
        ]

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
