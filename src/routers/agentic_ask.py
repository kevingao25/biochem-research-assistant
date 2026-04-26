from fastapi import APIRouter, HTTPException

from src.dependencies import AgenticRAGDep
from src.schemas.api.ask import AgenticAskResponse, AskRequest

router = APIRouter(tags=["agentic-rag"])


@router.post("/ask-agentic", response_model=AgenticAskResponse)
async def ask_agentic(request: AskRequest, agentic_rag: AgenticRAGDep) -> AgenticAskResponse:
    """Answer with an adaptive LangGraph retrieval workflow."""
    try:
        result = await agentic_rag.ask(
            query=request.query,
            top_k=request.top_k,
            model=request.model,
            use_hybrid=request.use_hybrid,
            categories=request.categories,
        )
        chunks = result.get("chunks", [])
        return AgenticAskResponse(
            query=request.query,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            chunks_used=len(chunks),
            search_mode=result.get("search_mode", "bm25"),
            reasoning_steps=result.get("reasoning_steps", []),
            retrieval_attempts=result.get("retrieval_attempts", 0),
            rewritten_query=result.get("rewritten_query"),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agentic RAG failed: {e}")
