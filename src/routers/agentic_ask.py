from fastapi import APIRouter, HTTPException

from src.dependencies import AgenticRAGDep, LangfuseDep
from src.schemas.api.ask import AgenticAskResponse, AskRequest, FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["agentic-rag"])


@router.post("/ask-agentic", response_model=AgenticAskResponse)
async def ask_agentic(request: AskRequest, agentic_rag: AgenticRAGDep, langfuse: LangfuseDep) -> AgenticAskResponse:
    """Answer with an adaptive LangGraph retrieval workflow."""
    try:
        with langfuse.trace_rag_request(
            query=request.query,
            user_id="api_user",
            metadata={"endpoint": "ask-agentic", "top_k": request.top_k, "use_hybrid": request.use_hybrid},
        ) as trace:
            result = await agentic_rag.ask(
                query=request.query,
                top_k=request.top_k,
                model=request.model,
                use_hybrid=request.use_hybrid,
                categories=request.categories,
            )
            trace_id = langfuse.get_trace_id(trace)
            langfuse.update_span(
                trace,
                output={
                    "answer": result.get("answer", ""),
                    "chunks_used": len(result.get("chunks", [])),
                    "retrieval_attempts": result.get("retrieval_attempts", 0),
                },
                metadata={"search_mode": result.get("search_mode", "bm25")},
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
            trace_id=trace_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agentic RAG failed: {e}")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest, langfuse: LangfuseDep) -> FeedbackResponse:
    """Attach user feedback to a Langfuse trace."""
    success = langfuse.submit_feedback(
        trace_id=request.trace_id,
        score=request.score,
        comment=request.comment,
    )
    if not success:
        raise HTTPException(status_code=503, detail="Langfuse feedback is unavailable")
    return FeedbackResponse(success=True, message="Feedback recorded successfully")
