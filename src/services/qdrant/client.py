import logging
import uuid
from typing import Any

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

from src.schemas.indexing.models import TextChunk

logger = logging.getLogger(__name__)

COLLECTION = "papers_chunks"
BM25_MODEL = "Qdrant/bm25"
DENSE_DIMENSIONS = 1024
PAYLOAD_INDEXES = {
    "categories": models.PayloadSchemaType.KEYWORD,
    "published_date": models.PayloadSchemaType.DATETIME,
}


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
        """Create the papers_chunks collection if it does not exist."""
        existing = {c.name for c in self.client.get_collections().collections}

        if COLLECTION in existing:
            info = self.client.get_collection(COLLECTION)
            has_dense = "dense" in (info.config.params.vectors or {})
            if has_dense:
                logger.info(f"Qdrant collection '{COLLECTION}' already exists with dense vectors")
                self._ensure_payload_indexes()
                return
            raise RuntimeError(
                f"Qdrant collection '{COLLECTION}' exists without the required dense vector field. "
                "Run a migration or reindex into a fresh collection before starting the service."
            )

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
        self._ensure_payload_indexes()
        logger.info(f"Qdrant collection '{COLLECTION}' created with BM25 + dense vectors")

    def _ensure_payload_indexes(self) -> None:
        """Create filter/sort indexes for paper metadata stored on each chunk."""
        for field_name, field_schema in PAYLOAD_INDEXES.items():
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception as e:
                # Qdrant treats existing indexes as an error in some versions.
                logger.debug(f"Payload index '{field_name}' already exists or could not be created: {e}")

    def index_chunk(
        self,
        chunk: TextChunk,
        dense_embedding: list[float] | None = None,
        paper_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a single text chunk with BM25 sparse vector and optional dense embedding."""
        sparse_embedding = next(iter(self.encoder.embed([chunk.text])))

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

        payload = {
            "arxiv_id": chunk.arxiv_id,
            "paper_id": chunk.paper_id,
            "chunk_index": chunk.metadata.chunk_index,
            "chunk_text": chunk.text,
            "section_title": chunk.metadata.section_title,
            "word_count": chunk.metadata.word_count,
        }
        if paper_metadata:
            payload.update(paper_metadata)

        self.client.upsert(
            collection_name=COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    payload=payload,
                    vector=vector,
                )
            ],
        )

    def index_chunks(
        self,
        chunks: list[TextChunk],
        dense_embeddings: list[list[float]] | None = None,
        paper_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Batch-index a list of chunks for one paper."""
        for i, chunk in enumerate(chunks):
            embedding = dense_embeddings[i] if dense_embeddings else None
            self.index_chunk(chunk, dense_embedding=embedding, paper_metadata=paper_metadata)
        logger.info(f"Indexed {len(chunks)} chunks for {chunks[0].arxiv_id if chunks else '?'}")

    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        categories: list[str] | None = None,
        latest: bool = False,
        min_score: float = 0.0,
    ) -> list[dict]:
        """BM25 keyword search over chunk text."""
        query_embedding = next(iter(self.encoder.query_embed(query)))
        results = self.client.query_points(
            collection_name=COLLECTION,
            query=models.SparseVector(
                indices=query_embedding.indices.tolist(),
                values=query_embedding.values.tolist(),
            ),
            using="bm25",
            query_filter=self._build_filter(categories),
            limit=self._fetch_limit(limit, offset, latest),
            score_threshold=min_score or None,
        )
        return self._slice_results(self._format(results.points), limit=limit, offset=offset, latest=latest)

    def search_hybrid(
        self,
        query: str,
        dense_embedding: list[float],
        limit: int = 10,
        offset: int = 0,
        categories: list[str] | None = None,
        latest: bool = False,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Hybrid BM25 + dense search using Qdrant's native RRF fusion.

        Qdrant fetches at least the requested limit from each index independently (prefetch),
        then merges them with Reciprocal Rank Fusion before returning `limit` results.
        """
        query_sparse = next(iter(self.encoder.query_embed(query)))
        fetch_limit = self._fetch_limit(limit, offset, latest)
        prefetch_limit = max(20, fetch_limit)

        results = self.client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                models.Prefetch(
                    query=models.SparseVector(
                        indices=query_sparse.indices.tolist(),
                        values=query_sparse.values.tolist(),
                    ),
                    using="bm25",
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=dense_embedding,
                    using="dense",
                    limit=prefetch_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=self._build_filter(categories),
            limit=fetch_limit,
            score_threshold=min_score or None,
        )
        return self._slice_results(self._format(results.points), limit=limit, offset=offset, latest=latest)

    def _build_filter(self, categories: list[str] | None = None) -> models.Filter | None:
        if not categories:
            return None
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="categories",
                    match=models.MatchAny(any=categories),
                )
            ]
        )

    def _fetch_limit(self, limit: int, offset: int, latest: bool) -> int:
        # When sorting by date after retrieval, pull a larger candidate pool first.
        return max(limit + offset, 100) if latest else limit + offset

    def _slice_results(self, hits: list[dict], limit: int, offset: int, latest: bool) -> list[dict]:
        if latest:
            hits = sorted(hits, key=lambda h: h.get("published_date") or "", reverse=True)
        return hits[offset : offset + limit]

    def _format(self, points) -> list[dict]:
        return [
            {
                "arxiv_id": point.payload["arxiv_id"],
                "paper_id": point.payload["paper_id"],
                "chunk_index": point.payload["chunk_index"],
                "chunk_text": point.payload["chunk_text"],
                "section_title": point.payload.get("section_title"),
                "title": point.payload.get("title", ""),
                "authors": point.payload.get("authors"),
                "abstract": point.payload.get("abstract"),
                "categories": point.payload.get("categories"),
                "published_date": point.payload.get("published_date"),
                "pdf_url": point.payload.get("pdf_url"),
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
