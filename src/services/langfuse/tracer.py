import logging
import time
from contextlib import contextmanager

from src.services.langfuse.client import LangfuseTracer

logger = logging.getLogger(__name__)


class RAGTracer:
    """RAG-specific tracing layer — wraps LangfuseTracer with typed operations."""

    def __init__(self, tracer: LangfuseTracer):
        self.tracer = tracer

    @contextmanager
    def trace_request(self, query: str):
        with self.tracer.trace_rag_request(query=query, user_id="api_user") as trace:
            try:
                yield trace
            finally:
                if trace:
                    self.tracer.flush()

    @contextmanager
    def trace_embedding(self, trace, query: str):
        start = time.time()
        span = self.tracer.create_span(trace, "query_embedding", {"query": query})
        try:
            yield span
        finally:
            if span:
                self.tracer.update_span(span, {"duration_ms": round((time.time() - start) * 1000, 2)})
                span.end()

    @contextmanager
    def trace_search(self, trace, query: str, top_k: int):
        span = self.tracer.create_span(trace, "search_retrieval", {"query": query, "top_k": top_k})
        try:
            yield span
        finally:
            if span:
                span.end()

    def end_search(self, span, chunks: list[dict], arxiv_ids: list[str], total_hits: int):
        if not span:
            return
        self.tracer.update_span(
            span,
            {
                "chunks_returned": len(chunks),
                "unique_papers": len(set(arxiv_ids)),
                "total_hits": total_hits,
            },
        )

    @contextmanager
    def trace_prompt_construction(self, trace, chunks: list[dict]):
        span = self.tracer.create_span(trace, "prompt_construction", {"chunk_count": len(chunks)})
        try:
            yield span
        finally:
            if span:
                span.end()

    def end_prompt(self, span, prompt: str):
        if not span:
            return
        self.tracer.update_span(
            span,
            {
                "prompt_length": len(prompt),
                "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            },
        )

    @contextmanager
    def trace_generation(self, trace, model: str, prompt: str):
        span = self.tracer.create_span(trace, "llm_generation", {"model": model, "prompt_length": len(prompt)})
        try:
            yield span
        finally:
            if span:
                span.end()

    def end_generation(self, span, response: str, model: str):
        if not span:
            return
        self.tracer.update_span(span, {"response": response, "response_length": len(response), "model": model})

    def end_request(self, trace, response: str, total_duration: float):
        if not trace:
            return
        try:
            trace.update(
                output={
                    "answer": response,
                    "total_duration_seconds": round(total_duration, 3),
                }
            )
        except Exception as e:
            logger.error(f"Langfuse end_request error: {e}")
