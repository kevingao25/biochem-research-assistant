import logging
import uuid
from typing import List

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models

from src.models.paper import Paper
from src.schemas.indexing.models import TextChunk

logger = logging.getLogger(__name__)

COLLECTION = "papers_chunks"
BM25_MODEL = "Qdrant/bm25"


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
        """Create the papers_chunks collection if it doesn't exist."""
        existing = {c.name for c in self.client.get_collections().collections}
        if COLLECTION in existing:
            logger.info(f"Qdrant collection '{COLLECTION}' already exists")
            return

        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config={},
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(),
            },
        )
        logger.info(f"Qdrant collection '{COLLECTION}' created with BM25 sparse vectors")

    def index_chunk(self, chunk: TextChunk) -> None:
        """Index a single text chunk as a BM25 sparse vector point."""
        embedding = next(self.encoder.embed([chunk.text]))

        # Deterministic UUID from arxiv_id + chunk_index so re-indexing is idempotent.
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.arxiv_id}_{chunk.metadata.chunk_index}"))

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
                    vector={
                        "bm25": models.SparseVector(
                            indices=embedding.indices.tolist(),
                            values=embedding.values.tolist(),
                        )
                    },
                )
            ],
        )

    def index_chunks(self, chunks: List[TextChunk]) -> None:
        """Batch-index a list of chunks for one paper."""
        for chunk in chunks:
            self.index_chunk(chunk)
        logger.info(f"Indexed {len(chunks)} chunks for {chunks[0].arxiv_id if chunks else '?'}")

    def index_paper(self, paper: Paper) -> None:
        """Legacy method kept for the backfill script — indexes the abstract as a single chunk."""
        from src.schemas.indexing.models import ChunkMetadata, TextChunk as TC
        chunk = TC(
            text=f"{paper.title}\n\nAbstract: {paper.abstract}",
            metadata=ChunkMetadata(chunk_index=0, word_count=len(paper.abstract.split()), section_title="Abstract"),
            arxiv_id=paper.arxiv_id,
            paper_id=str(paper.id),
        )
        self.index_chunk(chunk)

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
        return [
            {
                "arxiv_id": point.payload["arxiv_id"],
                "paper_id": point.payload["paper_id"],
                "chunk_index": point.payload["chunk_index"],
                "chunk_text": point.payload["chunk_text"],
                "section_title": point.payload.get("section_title"),
                "score": point.score,
            }
            for point in results.points
        ]

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
