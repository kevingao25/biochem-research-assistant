import logging
from typing import List

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client import models

from src.models.paper import Paper

logger = logging.getLogger(__name__)

COLLECTION = "papers"
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

    def index_paper(self, paper: Paper) -> None:
        embedding = next(self.encoder.embed([paper.abstract]))
        self.client.upsert(
            collection_name=COLLECTION,
            points=[
                models.PointStruct(
                    id=str(paper.id),
                    payload={
                        "arxiv_id": paper.arxiv_id,
                        "title": paper.title,
                        "authors": paper.authors,
                        "abstract": paper.abstract,
                        "categories": paper.categories,
                        "published_date": paper.published_date.isoformat(),
                        "pdf_url": paper.pdf_url,
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

    def search(self, query: str, limit: int = 10) -> List[dict]:
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
                "title": point.payload["title"],
                "authors": point.payload["authors"],
                "abstract": point.payload["abstract"],
                "categories": point.payload["categories"],
                "published_date": point.payload["published_date"],
                "pdf_url": point.payload["pdf_url"],
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
