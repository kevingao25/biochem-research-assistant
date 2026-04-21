import logging

from fastapi import APIRouter, HTTPException, Query

from src.dependencies import QdrantDep, SessionDep
from src.repositories.paper import PaperRepository
from src.schemas.api.papers import PaperResponse, SearchHit, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/papers", tags=["papers"])


# NOTE: /search must be declared before /{arxiv_id}.
# FastAPI matches routes top-to-bottom — if /{arxiv_id} came first,
# a request to /papers/search would match it with arxiv_id="search".
@router.get("/search", response_model=SearchResponse)
def search_papers(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    qdrant: QdrantDep = None,
):
    """BM25 keyword search over paper chunks via Qdrant sparse vectors."""
    hits = qdrant.search(q, limit=limit)
    return SearchResponse(
        query=q,
        total=len(hits),
        hits=[SearchHit(**hit) for hit in hits],
    )


@router.get("", response_model=list[PaperResponse])
def list_papers(
    session: SessionDep = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List recently ingested papers from PostgreSQL, newest first."""
    repo = PaperRepository(session)
    return repo.get_all(limit=limit, offset=offset)


@router.get("/{arxiv_id}", response_model=PaperResponse)
def get_paper(arxiv_id: str, session: SessionDep = None):
    """Fetch a single paper by its arXiv ID."""
    repo = PaperRepository(session)
    paper = repo.get_by_arxiv_id(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{arxiv_id}' not found")
    return paper
