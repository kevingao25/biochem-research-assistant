import json
import logging
import time
from typing import AsyncIterator, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.dependencies import CacheDep, JinaDep, LangfuseDep, OllamaDep, QdrantDep
from src.schemas.api.ask import AskRequest, AskResponse
from src.services.langfuse.tracer import RAGTracer

logger = logging.getLogger(__name__)

ask_router = APIRouter(tags=["ask"])
stream_router = APIRouter(tags=["stream"])


def _build_user_message(query: str, chunks: List[Dict]) -> str:
    """Format retrieved chunks + question into the user message for the LLM."""
    parts = ["### Context from Papers:\n"]
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}. arXiv:{chunk['arxiv_id']}]")
        parts.append(chunk["chunk_text"])
        parts.append("")
    parts.append(f"### Question:\n{query}")
    return "\n".join(parts)


def _extract_sources(chunks: List[Dict]) -> List[str]:
    """Build deduplicated arXiv PDF URLs from chunk metadata."""
    seen: set = set()
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


async def _retrieve_chunks(
    request: AskRequest,
    qdrant,
    jina,
    rag_tracer: RAGTracer,
    trace,
) -> tuple[List[Dict], List[str], str]:
    """Retrieve chunks, build source URLs, return (chunks, sources, search_mode)."""
    query_embedding = None
    search_mode = "bm25"

    if request.use_hybrid:
        with rag_tracer.trace_embedding(trace, request.query) as emb_span:
            try:
                query_embedding = await jina.embed_query(request.query)
                search_mode = "hybrid"
            except Exception as e:
                logger.warning(f"Embedding failed, falling back to BM25: {e}")
                if emb_span:
                    rag_tracer.tracer.update_span(emb_span, {"success": False, "error": str(e)})

    with rag_tracer.trace_search(trace, request.query, request.top_k) as search_span:
        if query_embedding is not None:
            raw_hits = qdrant.search_hybrid(request.query, dense_embedding=query_embedding, limit=request.top_k)
        else:
            raw_hits = qdrant.search(request.query, limit=request.top_k)
            search_mode = "bm25"

        chunks = []
        seen_urls: set = set()
        sources = []
        arxiv_ids = []

        for hit in raw_hits:
            arxiv_id = hit.get("arxiv_id", "")
            chunks.append({"arxiv_id": arxiv_id, "chunk_text": hit.get("chunk_text", "")})
            if arxiv_id:
                arxiv_ids.append(arxiv_id)
                clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
                url = f"https://arxiv.org/pdf/{clean_id}.pdf"
                if url not in seen_urls:
                    sources.append(url)
                    seen_urls.add(url)

        rag_tracer.end_search(search_span, chunks, arxiv_ids, len(raw_hits))

    return chunks, sources, search_mode


@ask_router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    qdrant: QdrantDep,
    jina: JinaDep,
    ollama: OllamaDep,
    cache: CacheDep,
    langfuse: LangfuseDep,
) -> AskResponse:
    """Answer a question using hybrid search + Ollama LLM."""
    rag_tracer = RAGTracer(langfuse)
    start_time = time.time()

    with rag_tracer.trace_request(request.query) as trace:
        try:
            # Cache check
            if cache:
                cached = await cache.find_cached_response(request)
                if cached:
                    return cached

            chunks, sources, search_mode = await _retrieve_chunks(request, qdrant, jina, rag_tracer, trace)

            if not chunks:
                response = AskResponse(
                    query=request.query,
                    answer="I couldn't find any relevant papers to answer your question. Try different keywords.",
                    sources=[],
                    chunks_used=0,
                    search_mode=search_mode,
                )
                rag_tracer.end_request(trace, response.answer, time.time() - start_time)
                return response

            # Build prompt
            with rag_tracer.trace_prompt_construction(trace, chunks) as prompt_span:
                from src.services.ollama.prompts import RAGPromptBuilder
                prompt_builder = RAGPromptBuilder()
                final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)
                rag_tracer.end_prompt(prompt_span, final_prompt)

            # Generate
            with rag_tracer.trace_generation(trace, request.model, final_prompt) as gen_span:
                rag_response = await ollama.generate_rag_answer(
                    query=request.query, chunks=chunks, model=request.model
                )
                answer = rag_response.get("answer", "Unable to generate answer")
                rag_tracer.end_generation(gen_span, answer, request.model)

            response = AskResponse(
                query=request.query,
                answer=answer,
                sources=sources,
                chunks_used=len(chunks),
                search_mode=search_mode,
            )
            rag_tracer.end_request(trace, answer, time.time() - start_time)

            # Cache the result
            if cache:
                try:
                    await cache.store_response(request, response)
                except Exception as e:
                    logger.warning(f"Cache store failed: {e}")

            return response

        except Exception as e:
            logger.error(f"Ask error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@stream_router.post("/stream")
async def ask_question_stream(
    request: AskRequest,
    qdrant: QdrantDep,
    jina: JinaDep,
    ollama: OllamaDep,
    cache: CacheDep,
    langfuse: LangfuseDep,
) -> StreamingResponse:
    """Stream the answer token-by-token using Server-Sent Events."""

    async def generate() -> AsyncIterator[str]:
        rag_tracer = RAGTracer(langfuse)
        start_time = time.time()

        with rag_tracer.trace_request(request.query) as trace:
            try:
                # Cache hit: re-stream word-by-word
                if cache:
                    cached = await cache.find_cached_response(request)
                    if cached:
                        yield f"data: {json.dumps({'sources': cached.sources, 'chunks_used': cached.chunks_used, 'search_mode': cached.search_mode})}\n\n"
                        for word in cached.answer.split():
                            yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
                        yield f"data: {json.dumps({'answer': cached.answer, 'done': True})}\n\n"
                        return

                chunks, sources, search_mode = await _retrieve_chunks(request, qdrant, jina, rag_tracer, trace)

                yield f"data: {json.dumps({'sources': sources, 'chunks_used': len(chunks), 'search_mode': search_mode})}\n\n"

                if not chunks:
                    yield f"data: {json.dumps({'answer': 'No relevant papers found.', 'done': True})}\n\n"
                    return

                # Build prompt
                with rag_tracer.trace_prompt_construction(trace, chunks) as prompt_span:
                    from src.services.ollama.prompts import RAGPromptBuilder
                    final_prompt = RAGPromptBuilder().create_rag_prompt(request.query, chunks)
                    rag_tracer.end_prompt(prompt_span, final_prompt)

                # Stream generation
                with rag_tracer.trace_generation(trace, request.model, final_prompt) as gen_span:
                    full_response = ""
                    async for chunk in ollama.generate_rag_answer_stream(
                        query=request.query, chunks=chunks, model=request.model
                    ):
                        if chunk.get("response"):
                            text = chunk["response"]
                            full_response += text
                            yield f"data: {json.dumps({'chunk': text})}\n\n"
                        if chunk.get("done", False):
                            rag_tracer.end_generation(gen_span, full_response, request.model)
                            yield f"data: {json.dumps({'answer': full_response, 'done': True})}\n\n"
                            break

                rag_tracer.end_request(trace, full_response, time.time() - start_time)

                if cache and full_response:
                    await cache.store_response(request, AskResponse(
                        query=request.query, answer=full_response,
                        sources=sources, chunks_used=len(chunks), search_mode=search_mode,
                    ))

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
