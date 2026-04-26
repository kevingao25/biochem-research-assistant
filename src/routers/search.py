import logging

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from src.dependencies import JinaDep, QdrantDep
from src.schemas.api.search import HybridSearchRequest, SearchHit, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    qdrant: QdrantDep,
    jina: JinaDep,
) -> SearchResponse:
    """Search paper chunks with BM25 or hybrid (BM25 + dense) mode."""
    try:
        if not await run_in_threadpool(qdrant.health_check):
            raise HTTPException(status_code=503, detail="Search service unavailable")

        query_embedding = None
        search_mode = "bm25"

        if request.use_hybrid:
            try:
                query_embedding = await jina.embed_query(request.query)
                search_mode = "hybrid"
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to BM25: {e}")

        if query_embedding is not None:
            raw_hits = await run_in_threadpool(
                qdrant.search_hybrid,
                request.query,
                dense_embedding=query_embedding,
                limit=request.size,
                offset=request.from_,
                categories=request.categories,
                latest=request.latest_papers,
                min_score=request.min_score,
            )
        else:
            raw_hits = await run_in_threadpool(
                qdrant.search,
                request.query,
                limit=request.size,
                offset=request.from_,
                categories=request.categories,
                latest=request.latest_papers,
                min_score=request.min_score,
            )

        hits = [
            SearchHit(
                arxiv_id=h.get("arxiv_id", ""),
                title=h.get("title", ""),
                authors=h.get("authors"),
                abstract=h.get("abstract"),
                categories=h.get("categories"),
                published_date=h.get("published_date"),
                pdf_url=h.get("pdf_url"),
                score=h.get("score", 0.0),
                chunk_text=h.get("chunk_text"),
                section_title=h.get("section_title"),
            )
            for h in raw_hits
        ]

        return SearchResponse.model_validate(
            {
                "query": request.query,
                "total": len(hits),
                "hits": hits,
                "size": request.size,
                "from": request.from_,
                "search_mode": search_mode,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
