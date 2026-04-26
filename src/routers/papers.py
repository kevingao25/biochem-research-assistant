import logging

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from src.dependencies import JinaDep, QdrantDep, SessionDep
from src.repositories.paper import PaperRepository
from src.schemas.api.papers import PaperResponse, SearchHit, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/papers", tags=["papers"])


# NOTE: /search must be declared before /{arxiv_id}.
# FastAPI matches routes top-to-bottom — if /{arxiv_id} came first,
# a request to /papers/search would match it with arxiv_id="search".
@router.get("/search", response_model=SearchResponse)
async def search_papers(
    qdrant: QdrantDep,
    jina: JinaDep,
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    categories: list[str] | None = Query(None, description="Optional arXiv category filters"),
):
    """Hybrid BM25 + dense search using Qdrant native RRF fusion.

    Falls back to BM25-only if Jina is unreachable so the endpoint stays
    available even when the embedding API is down.
    """
    try:
        dense_embedding = await jina.embed_query(q)
        hits = await run_in_threadpool(
            qdrant.search_hybrid,
            q,
            dense_embedding=dense_embedding,
            limit=limit,
            categories=categories,
        )
        search_mode = "hybrid"
    except Exception as e:
        logger.warning(f"Jina embedding failed, falling back to BM25: {e}")
        hits = await run_in_threadpool(qdrant.search, q, limit=limit, categories=categories)
        search_mode = "bm25"

    return SearchResponse(
        query=q,
        total=len(hits),
        hits=[SearchHit(**hit) for hit in hits],
        search_mode=search_mode,
    )


@router.get("", response_model=list[PaperResponse])
def list_papers(
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List recently ingested papers from PostgreSQL, newest first."""
    repo = PaperRepository(session)
    return repo.get_all(limit=limit, offset=offset)


@router.get("/{arxiv_id}", response_model=PaperResponse)
def get_paper(arxiv_id: str, session: SessionDep):
    """Fetch a single paper by its arXiv ID."""
    repo = PaperRepository(session)
    paper = repo.get_by_arxiv_id(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{arxiv_id}' not found")
    return paper
