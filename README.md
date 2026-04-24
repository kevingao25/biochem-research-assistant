# Biochem Research Assistant

A production RAG system that ingests biochemistry papers from arXiv, indexes them semantically, and lets you search and ask questions using natural language. Built for a biochem PhD student researching phage-bacteria defense mechanisms.

## Stack

| Service    | Version  | Purpose                             |
|------------|----------|-------------------------------------|
| FastAPI    | 0.115.12 | REST API                            |
| PostgreSQL | 17       | Paper metadata storage              |
| Qdrant     | 1.17.1   | Vector search (BM25 + dense hybrid) |
| Airflow    | 3.2.0    | Daily arXiv ingestion pipeline      |
| Ollama     | latest   | Local LLM inference (llama3.2:1b)   |
| Redis      | 7.4.0    | Exact-match answer cache            |
| Jina AI    | cloud    | Dense embeddings (jina-embeddings-v3)|
| Langfuse   | cloud    | LLM observability and tracing       |

## Quick Start

```bash
cp .env.example .env   # fill in secrets (see Environment Variables below)
make start             # build and start all services
make health            # verify all services are healthy

# Pull the LLM model into Ollama on first run
docker compose exec ollama ollama pull llama3.2:1b
```

## Endpoints

| URL | What it does |
|-----|-------------|
| `POST /api/v1/ask` | Ask a question — returns a grounded answer with citations |
| `POST /api/v1/ask/stream` | Same but streams the answer token-by-token (SSE) |
| `POST /api/v1/search/` | Hybrid BM25 + semantic search over paper chunks |
| `GET /api/v1/papers` | List recently ingested papers |
| `GET /api/v1/papers/{arxiv_id}` | Get a single paper by arXiv ID |
| `GET /api/v1/papers/search?q=...` | Full-text search by query string |
| `GET /api/v1/health` | Per-service health status (typed JSON) |
| `GET /docs` | Interactive API docs (Swagger) |
| `http://localhost:8080` | Airflow UI (admin / see .env) |
| `http://localhost:6333/dashboard` | Qdrant dashboard |

## Architecture

```
                        ┌─────────────────────────────────────────────────┐
                        │                   Airflow DAG                   │
                        │              (daily, 3 arXiv categories)        │
                        └──────────────────────┬──────────────────────────┘
                                               │
                          ┌────────────────────▼────────────────────┐
                          │               arXiv API                  │
                          └────────────────────┬────────────────────┘
                                               │ paper metadata + PDFs
                    ┌──────────────────────────▼──────────────────────────┐
                    │                    Ingestion Pipeline                │
                    │  fetch → parse (docling) → chunk → embed (Jina AI)  │
                    └──────────┬───────────────────────────┬──────────────┘
                               │                           │
               ┌───────────────▼──────┐       ┌───────────▼───────────┐
               │     PostgreSQL       │       │        Qdrant          │
               │   paper metadata     │       │  BM25 sparse + dense   │
               └──────────────────────┘       │     vector index       │
                                              └───────────┬───────────┘
                                                          │
┌──────────┐    ┌────────────────────────────────────────▼────────────────────────────┐
│  Client  │───▶│                          FastAPI                                     │
└──────────┘    │                                                                      │
                │  POST /ask                                                           │
                │    1. Redis cache hit? ──yes──▶ return cached answer                │
                │         │ no                                                         │
                │    2. Jina AI embed query                                            │
                │    3. Qdrant hybrid search (BM25 + dense) → top-K chunks            │
                │    4. Build prompt with paper excerpts                               │
                │    5. Ollama (llama3.2:1b) → grounded answer                        │
                │    6. Store in Redis cache                                           │
                │    7. Trace all steps → Langfuse                                    │
                └───────┬──────────┬───────────────┬──────────┬────────────────────┘
                        │          │               │          │
               ┌────────▼──┐  ┌────▼────┐  ┌──────▼───┐  ┌──▼──────────┐
               │   Redis   │  │ Jina AI │  │  Ollama  │  │  Langfuse   │
               │   cache   │  │ (cloud) │  │ (local)  │  │  (cloud)    │
               └───────────┘  └─────────┘  └──────────┘  └─────────────┘
```

## Project Structure

```
src/
├── config.py               — centralized settings (pydantic-settings)
├── exceptions.py           — typed exception hierarchy
├── dependencies.py         — FastAPI dependency injection
├── db/
│   ├── base.py             — ORM models
│   ├── factory.py          — make_database()
│   └── interfaces/
│       ├── base.py         — BaseDatabase ABC
│       └── postgresql.py   — PostgreSQLDatabase implementation
├── routers/
│   ├── ask.py              — POST /ask, POST /ask/stream
│   ├── health.py           — GET /health (typed per-service status)
│   ├── papers.py           — GET /papers, GET /papers/{id}
│   └── search.py           — POST /search (hybrid BM25 + dense)
├── schemas/
│   ├── api/                — request/response models (ask, health, papers, search)
│   ├── arxiv/              — arXiv paper schemas
│   ├── database/           — database config schemas
│   ├── embeddings/         — Jina config schemas
│   ├── indexing/           — chunk/index schemas
│   └── pdf_parser/         — PDF parsing schemas
└── services/
    ├── arxiv/              — ArxivClient + factory
    ├── cache/              — CacheClient + factory (Redis)
    ├── jina/               — JinaClient + factory (embeddings)
    ├── langfuse/           — LangfuseTracer + RAGTracer + factory
    ├── ollama/             — OllamaClient + RAGPromptBuilder + factory
    ├── pdf_parser/         — PDFProcessor + factory
    └── qdrant/             — QdrantService + factory

airflow/dags/
└── arxiv_ingestion/
    ├── common.py           — shared service initialization
    ├── fetching.py         — fetch papers from arXiv → Postgres
    ├── indexing.py         — download PDFs → chunk → embed → Qdrant
    └── reporting.py        — log ingestion stats
```

## How It Works

**Ingestion pipeline** (runs daily via Airflow):
1. Fetch yesterday's papers from arXiv (`q-bio.BM`, `q-bio.MN`, `q-bio.GN`)
2. Store metadata in PostgreSQL
3. Download PDFs and parse into sections with docling
4. Chunk sections into ~600-word overlapping windows
5. Generate dense embeddings via Jina AI
6. Index chunks (BM25 sparse + dense vectors) into Qdrant

**Search** (`POST /api/v1/search/`):
- Encodes query with Jina AI → hybrid BM25 + dense search via Qdrant RRF fusion
- Falls back to BM25-only if Jina is unreachable
- Supports `min_score` filtering and offset-based pagination

**Q&A** (`POST /api/v1/ask`):
1. Check Redis cache — return instantly if the same question was asked before
2. Hybrid search → retrieve top-K relevant chunks
3. Build a prompt with paper excerpts as context
4. Call Ollama (local LLM) → grounded answer with arXiv citations
5. Cache the answer in Redis for next time
6. Trace all steps in Langfuse for observability

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Where to get it |
|----------|----------------|
| `JINA_API_KEY` | [jina.ai](https://jina.ai) |
| `LANGFUSE_PUBLIC_KEY` | [cloud.langfuse.com](https://cloud.langfuse.com) |
| `LANGFUSE_SECRET_KEY` | [cloud.langfuse.com](https://cloud.langfuse.com) |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` |
| `REDIS_URL` | `redis://redis:6379` (local Docker) |

## arXiv Categories Ingested

- `q-bio.BM` — Biomolecules
- `q-bio.MN` — Molecular Networks
- `q-bio.GN` — Genomics

## Common Commands

```bash
make setup      # install Python dependencies (uv sync)
make start      # build and start all services
make stop       # stop all services
make restart    # restart without rebuild
make logs       # stream logs from all services
make health     # check health of all services (colored ✓/✗ per service)
make status     # show container status
make test       # run all tests
make lint       # ruff check + mypy
make format     # ruff format
make test-cov   # tests with HTML coverage report

# Backfill Qdrant after a full restart (data is wiped on make start)
docker exec biochem-research-assistant-postgres-1 \
  psql -U biochem -d biochem_research -c "UPDATE papers SET pdf_processed=false;"
# Then trigger the DAG from the Airflow UI at http://localhost:8080
```
