import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from starlette.concurrency import run_in_threadpool

from src.config import Settings
from src.services.agents.prompts import GRADE_DOCUMENTS_PROMPT, GUARDRAIL_PROMPT, REWRITE_QUERY_PROMPT
from src.services.jina.client import JinaClient
from src.services.ollama.client import OllamaClient
from src.services.qdrant.client import QdrantService

logger = logging.getLogger(__name__)

_ARXIV_VERSION_SUFFIX = re.compile(r"v\d+$")
_SCOPE_TERMS = {
    "anti-phage",
    "bacteria",
    "bacterial",
    "bacteriophage",
    "biochem",
    "biochemistry",
    "biomolecule",
    "crispr",
    "defense",
    "dna",
    "gene",
    "genome",
    "genomic",
    "immunity",
    "molecular",
    "phage",
    "protein",
    "rna",
}


class AgentState(TypedDict, total=False):
    query: str
    active_query: str
    answer: str
    chunks: list[dict[str, Any]]
    sources: list[str]
    search_mode: str
    reasoning_steps: list[str]
    retrieval_attempts: int
    rewritten_query: str | None
    guardrail_passed: bool
    documents_relevant: bool


@dataclass(frozen=True)
class AgentContext:
    qdrant: QdrantService
    jina: JinaClient
    ollama: OllamaClient
    model: str
    top_k: int
    use_hybrid: bool
    categories: list[str] | None
    max_retrieval_attempts: int
    guardrail_enabled: bool


class AgenticRAGService:
    """LangGraph workflow that can adapt retrieval before generating an answer."""

    def __init__(
        self,
        qdrant: QdrantService,
        jina: JinaClient,
        ollama: OllamaClient,
        settings: Settings,
    ):
        self.qdrant = qdrant
        self.jina = jina
        self.ollama = ollama
        self.settings = settings
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState, context_schema=AgentContext)
        workflow.add_node("guardrail", self._guardrail)
        workflow.add_node("out_of_scope", self._out_of_scope)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("grade_documents", self._grade_documents)
        workflow.add_node("rewrite_query", self._rewrite_query)
        workflow.add_node("no_relevant_docs", self._no_relevant_docs)
        workflow.add_node("generate_answer", self._generate_answer)

        workflow.add_edge(START, "guardrail")
        workflow.add_conditional_edges(
            "guardrail",
            self._route_after_guardrail,
            {"continue": "retrieve", "out_of_scope": "out_of_scope"},
        )
        workflow.add_edge("out_of_scope", END)
        workflow.add_edge("retrieve", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            self._route_after_grading,
            {
                "generate_answer": "generate_answer",
                "rewrite_query": "rewrite_query",
                "no_relevant_docs": "no_relevant_docs",
            },
        )
        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("no_relevant_docs", END)
        workflow.add_edge("generate_answer", END)
        return workflow.compile()

    async def ask(
        self,
        query: str,
        top_k: int,
        model: str,
        use_hybrid: bool,
        categories: list[str] | None = None,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        context = AgentContext(
            qdrant=self.qdrant,
            jina=self.jina,
            ollama=self.ollama,
            model=model,
            top_k=top_k,
            use_hybrid=use_hybrid,
            categories=categories,
            max_retrieval_attempts=self.settings.agent.max_retrieval_attempts,
            guardrail_enabled=self.settings.agent.guardrail_enabled,
        )
        initial_state: AgentState = {
            "query": query,
            "active_query": query,
            "reasoning_steps": [],
            "retrieval_attempts": 0,
            "chunks": [],
            "sources": [],
            "search_mode": "bm25",
            "rewritten_query": None,
        }
        return await self.graph.ainvoke(initial_state, context=context)

    async def _guardrail(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        if not runtime.context.guardrail_enabled:
            return {
                "guardrail_passed": True,
                "reasoning_steps": self._add_reasoning(state, "Skipped guardrail because it is disabled."),
            }

        query = state["query"]
        allowed = self._heuristic_scope_check(query)
        reason = "Matched biochemistry domain terms." if allowed else "No obvious biochemistry domain terms found."

        try:
            data = await self._generate_json(
                runtime.context.ollama,
                runtime.context.model,
                GUARDRAIL_PROMPT.format(query=query),
            )
            allowed = bool(data.get("allowed", allowed))
            reason = str(data.get("reason", reason))
        except Exception as e:
            logger.warning(f"Guardrail LLM check failed, using heuristic fallback: {e}")

        return {
            "guardrail_passed": allowed,
            "reasoning_steps": self._add_reasoning(state, f"Guardrail {'passed' if allowed else 'blocked'}: {reason}"),
        }

    def _route_after_guardrail(self, state: AgentState) -> Literal["continue", "out_of_scope"]:
        return "continue" if state.get("guardrail_passed") else "out_of_scope"

    async def _out_of_scope(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        return {
            "answer": (
                "I can help with biochemistry and phage-bacteria research questions, but this question looks outside "
                "that research scope. Try asking about a molecular mechanism, organism, gene, protein, or defense system."
            ),
            "sources": [],
            "chunks": [],
            "search_mode": "none",
            "reasoning_steps": self._add_reasoning(state, "Answered without retrieval because the query was out of scope."),
        }

    async def _retrieve(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        active_query = state.get("active_query") or state["query"]
        attempts = state.get("retrieval_attempts", 0) + 1
        query_embedding = None
        search_mode = "bm25"

        if runtime.context.use_hybrid:
            try:
                query_embedding = await runtime.context.jina.embed_query(active_query)
                search_mode = "hybrid"
            except Exception as e:
                logger.warning(f"Agentic retrieval embedding failed, falling back to BM25: {e}")

        if query_embedding is not None:
            raw_hits = await run_in_threadpool(
                runtime.context.qdrant.search_hybrid,
                active_query,
                dense_embedding=query_embedding,
                limit=runtime.context.top_k,
                categories=runtime.context.categories,
            )
        else:
            raw_hits = await run_in_threadpool(
                runtime.context.qdrant.search,
                active_query,
                limit=runtime.context.top_k,
                categories=runtime.context.categories,
            )
            search_mode = "bm25"

        chunks = [
            {
                "arxiv_id": hit.get("arxiv_id", ""),
                "chunk_text": hit.get("chunk_text", ""),
                "title": hit.get("title", ""),
                "section_title": hit.get("section_title"),
                "score": hit.get("score", 0.0),
            }
            for hit in raw_hits
        ]
        return {
            "chunks": chunks,
            "sources": self._extract_sources(chunks),
            "search_mode": search_mode,
            "retrieval_attempts": attempts,
            "reasoning_steps": self._add_reasoning(
                state, f"Retrieved {len(chunks)} chunks with {search_mode} search on attempt {attempts}."
            ),
        }

    async def _grade_documents(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        chunks = state.get("chunks", [])
        if not chunks:
            return {
                "documents_relevant": False,
                "reasoning_steps": self._add_reasoning(state, "No chunks were retrieved, so the query needs rewriting."),
            }

        relevant = True
        reason = "Retrieved chunks are available."
        try:
            context = self._format_context(chunks)
            data = await self._generate_json(
                runtime.context.ollama,
                runtime.context.model,
                GRADE_DOCUMENTS_PROMPT.format(query=state["query"], context=context),
            )
            relevant = bool(data.get("relevant", relevant))
            reason = str(data.get("reason", reason))
        except Exception as e:
            logger.warning(f"Document grading failed, treating retrieved chunks as relevant: {e}")

        return {
            "documents_relevant": relevant,
            "reasoning_steps": self._add_reasoning(
                state, f"Document grading {'accepted' if relevant else 'rejected'} the retrieved chunks: {reason}"
            ),
        }

    def _route_after_grading(self, state: AgentState) -> Literal["generate_answer", "rewrite_query", "no_relevant_docs"]:
        if state.get("documents_relevant"):
            return "generate_answer"
        if state.get("retrieval_attempts", 0) >= self.settings.agent.max_retrieval_attempts:
            return "no_relevant_docs"
        return "rewrite_query"

    async def _rewrite_query(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        original_query = state["query"]
        rewritten_query = f"{original_query} phage bacteria molecular defense mechanism"
        reason = "Added domain-specific terms."

        try:
            data = await self._generate_json(
                runtime.context.ollama,
                runtime.context.model,
                REWRITE_QUERY_PROMPT.format(query=original_query),
            )
            rewritten_query = str(data.get("query", rewritten_query)).strip() or rewritten_query
            reason = str(data.get("reason", reason))
        except Exception as e:
            logger.warning(f"Query rewrite failed, using fallback rewrite: {e}")

        return {
            "active_query": rewritten_query,
            "rewritten_query": rewritten_query,
            "reasoning_steps": self._add_reasoning(state, f"Rewrote query for retrieval: {reason}"),
        }

    async def _no_relevant_docs(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        return {
            "answer": (
                "I could not find relevant indexed paper chunks after trying to improve the search query. "
                "Try using more specific gene, protein, organism, or defense-system terms."
            ),
            "sources": [],
            "chunks": [],
            "reasoning_steps": self._add_reasoning(state, "Stopped after the maximum retrieval attempts."),
        }

    async def _generate_answer(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        rag_response = await runtime.context.ollama.generate_rag_answer(
            query=state["query"],
            chunks=state.get("chunks", []),
            model=runtime.context.model,
        )
        answer = rag_response.get("answer", "Unable to generate answer")
        return {
            "answer": answer,
            "sources": state.get("sources", []),
            "reasoning_steps": self._add_reasoning(state, "Generated a grounded answer from the accepted chunks."),
        }

    async def _generate_json(self, ollama: OllamaClient, model: str, prompt: str) -> dict[str, Any]:
        response = await ollama.generate(model=model, prompt=prompt, temperature=0.0, format="json")
        text = (response or {}).get("response", "{}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group())

    def _heuristic_scope_check(self, query: str) -> bool:
        lower_query = query.lower()
        return any(term in lower_query for term in _SCOPE_TERMS)

    def _add_reasoning(self, state: AgentState, step: str) -> list[str]:
        return [*state.get("reasoning_steps", []), step]

    def _format_context(self, chunks: list[dict[str, Any]]) -> str:
        parts = []
        for i, chunk in enumerate(chunks[:5], 1):
            parts.append(f"[{i}] {chunk.get('chunk_text', '')[:800]}")
        return "\n\n".join(parts)

    def _extract_sources(self, chunks: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        sources = []
        for chunk in chunks:
            arxiv_id = chunk.get("arxiv_id", "")
            if not arxiv_id:
                continue
            clean_id = _ARXIV_VERSION_SUFFIX.sub("", arxiv_id)
            url = f"https://arxiv.org/pdf/{clean_id}.pdf"
            if url not in seen:
                seen.add(url)
                sources.append(url)
        return sources
