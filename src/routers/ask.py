import json
import logging
from typing import AsyncIterator, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.dependencies import CacheDep, JinaDep, LangfuseDep, OllamaDep, QdrantDep
from src.schemas.api.ask import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ask", tags=["ask"])


def _build_user_message(query: str, chunks: List[dict]) -> str:
    """Format retrieved chunks + question into the user message for the LLM."""
    parts = ["### Context from Papers:\n"]
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}. arXiv:{chunk['arxiv_id']}]")
        parts.append(chunk["chunk_text"])
        parts.append("")
    parts.append(f"### Question:\n{query}")
    return "\n".join(parts)


def _extract_sources(chunks: List[dict]) -> List[str]:
    """Build deduplicated arXiv PDF URLs from chunk metadata."""
    seen = set()
    sources = []
    for chunk in chunks:
        arxiv_id = chunk.get("arxiv_id", "")
        if arxiv_id:
            clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
            url = f"https://arxiv.org/pdf/{clean_id}.pdf"
            if url not in seen:
                seen.add(url)
                sources.append(url)
    return sources


async def _retrieve_chunks(request: AskRequest, qdrant, jina) -> tuple[List[dict], str]:
    """Run hybrid or BM25-only search. Returns (chunks, search_mode)."""
    if request.use_hybrid:
        try:
            embedding = await jina.embed_query(request.query)
            chunks = qdrant.search_hybrid(request.query, dense_embedding=embedding, limit=request.top_k)
            return chunks, "hybrid"
        except Exception as e:
            logger.warning(f"Hybrid search failed, falling back to BM25: {e}")

    chunks = qdrant.search(request.query, limit=request.top_k)
    return chunks, "bm25"


@router.post("", response_model=AskResponse)
async def ask(
    request: AskRequest,
    qdrant: QdrantDep,
    jina: JinaDep,
    ollama: OllamaDep,
    cache: CacheDep,
    langfuse: LangfuseDep,
):
    """Answer a question using hybrid search + Ollama LLM."""
    with langfuse.trace(query=request.query) as trace:

        # 1. Cache check — skip the whole pipeline if we've seen this exact request
        with langfuse.span(trace, "cache_lookup") as s:
            cached = await cache.get(request)
            if s:
                s.update(output={"hit": cached is not None})
        if cached:
            return cached

        # 2. Retrieve relevant chunks from Qdrant
        with langfuse.span(trace, "search", {"query": request.query, "top_k": request.top_k}) as s:
            chunks, search_mode = await _retrieve_chunks(request, qdrant, jina)
            if s:
                s.update(output={"chunks_found": len(chunks), "search_mode": search_mode})

        if not chunks:
            return AskResponse(
                query=request.query,
                answer="I couldn't find any relevant papers to answer your question. Try rephrasing or using different keywords.",
                sources=[],
                chunks_used=0,
                search_mode=search_mode,
            )

        # 3. Build prompt and extract source URLs
        user_message = _build_user_message(request.query, chunks)
        sources = _extract_sources(chunks)

        # 4. Generate answer with Ollama
        with langfuse.span(trace, "generation", {"model": request.model, "chunks_used": len(chunks)}) as s:
            try:
                answer = await ollama.generate(user_message, model=request.model)
            except Exception as e:
                logger.error(f"Ollama generation failed: {e}")
                raise HTTPException(status_code=503, detail="LLM service unavailable")
            if s:
                s.update(output={"answer_length": len(answer)})

        response = AskResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            chunks_used=len(chunks),
            search_mode=search_mode,
        )

        # 5. Cache for next time
        await cache.set(request, response)

        return response


# TODO: add Langfuse tracing to ask_stream — tracing a streaming response requires
# keeping the trace open while tokens arrive, then closing it on the done event.
# Needs a background task or a manual flush after the generator exhausts.
@router.post("/stream")
async def ask_stream(
    request: AskRequest,
    qdrant: QdrantDep,
    jina: JinaDep,
    ollama: OllamaDep,
    cache: CacheDep,
):
    """Stream the answer token-by-token using Server-Sent Events.

    Each event is a JSON object:
      {"sources": [...], "chunks_used": N, "search_mode": "hybrid"}  ← sent first
      {"chunk": "token "}                                              ← repeated
      {"done": true}                                                   ← final event
    """
    async def generate() -> AsyncIterator[str]:
        # Serve cached answer by re-streaming word-by-word
        cached = await cache.get(request)
        if cached:
            yield f"data: {json.dumps({'sources': cached.sources, 'chunks_used': cached.chunks_used, 'search_mode': cached.search_mode})}\n\n"
            for word in cached.answer.split():
                yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        chunks, search_mode = await _retrieve_chunks(request, qdrant, jina)
        sources = _extract_sources(chunks)

        # Send metadata first so the client can show sources before the answer arrives
        yield f"data: {json.dumps({'sources': sources, 'chunks_used': len(chunks), 'search_mode': search_mode})}\n\n"

        if not chunks:
            yield f"data: {json.dumps({'chunk': 'I could not find any relevant papers to answer your question.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        user_message = _build_user_message(request.query, chunks)
        full_answer = ""

        try:
            async for token in ollama.generate_stream(user_message, model=request.model):
                full_answer += token
                yield f"data: {json.dumps({'chunk': token})}\n\n"
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield f"data: {json.dumps({'error': 'LLM service unavailable'})}\n\n"
            return

        yield f"data: {json.dumps({'done': True})}\n\n"

        # Cache the full reconstructed answer after streaming completes
        if full_answer:
            await cache.set(request, AskResponse(
                query=request.query,
                answer=full_answer,
                sources=sources,
                chunks_used=len(chunks),
                search_mode=search_mode,
            ))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
