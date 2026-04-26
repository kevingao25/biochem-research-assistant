from src.schemas.indexing.models import ChunkMetadata, TextChunk
from src.services.qdrant.client import QdrantService


class _FakeArray:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeSparseEmbedding:
    indices = _FakeArray([1, 2, 3])
    values = _FakeArray([0.5, 0.25, 0.125])


class _FakeEncoder:
    def embed(self, _texts):
        return iter([_FakeSparseEmbedding()])


class _FakeClient:
    def __init__(self):
        self.points = []

    def upsert(self, collection_name, points):
        self.collection_name = collection_name
        self.points.extend(points)


def _service_without_network() -> QdrantService:
    service = object.__new__(QdrantService)
    service.client = _FakeClient()
    service._encoder = _FakeEncoder()
    return service


def test_index_chunk_stores_filterable_paper_payload():
    service = _service_without_network()
    chunk = TextChunk(
        text="Phage defense systems often involve CRISPR arrays.",
        arxiv_id="2401.00001",
        paper_id="paper-1",
        metadata=ChunkMetadata(chunk_index=0, word_count=8, section_title="Introduction"),
    )

    service.index_chunk(
        chunk,
        dense_embedding=[0.1, 0.2],
        paper_metadata={
            "title": "A phage defense paper",
            "authors": ["A. Researcher"],
            "abstract": "About bacterial defense.",
            "categories": ["q-bio.BM"],
            "published_date": "2026-01-01T00:00:00+00:00",
            "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
        },
    )

    payload = service.client.points[0].payload
    assert payload["categories"] == ["q-bio.BM"]
    assert payload["published_date"] == "2026-01-01T00:00:00+00:00"
    assert payload["title"] == "A phage defense paper"


def test_build_filter_matches_any_category():
    service = _service_without_network()

    qdrant_filter = service._build_filter(["q-bio.BM", "q-bio.GN"])

    assert qdrant_filter is not None
    assert qdrant_filter.must[0].key == "categories"
    assert qdrant_filter.must[0].match.any == ["q-bio.BM", "q-bio.GN"]


def test_latest_sort_happens_before_pagination():
    service = _service_without_network()
    hits = [
        {"arxiv_id": "old", "published_date": "2025-01-01T00:00:00+00:00"},
        {"arxiv_id": "new", "published_date": "2026-01-01T00:00:00+00:00"},
        {"arxiv_id": "mid", "published_date": "2025-06-01T00:00:00+00:00"},
    ]

    result = service._slice_results(hits, limit=2, offset=0, latest=True)

    assert [hit["arxiv_id"] for hit in result] == ["new", "mid"]
