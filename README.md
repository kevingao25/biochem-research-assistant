# Biochem Research Assistant

A RAG system that ingests biochemistry papers from arXiv and lets you search them by keyword or (soon) semantic similarity. Built for a biochem PhD student researching phage-bacteria defense mechanisms.

## Stack

| Service    | Version  | Purpose                        |
|------------|----------|--------------------------------|
| FastAPI    | 0.115.12 | REST API                       |
| PostgreSQL | 17       | Paper metadata storage         |
| Qdrant     | 1.17.1   | Vector search (BM25 + semantic)|
| Airflow    | 3.2.0    | Daily arXiv ingestion pipeline |
| Ollama     | latest   | Local LLM inference            |

## Quick Start

```bash
cp .env.example .env   # fill in secrets
make start             # build and start all services
make health            # verify all services are healthy
```

## Endpoints

| URL | What it does |
|-----|-------------|
| http://localhost:8000/api/v1/papers | List recent papers |
| http://localhost:8000/api/v1/papers/{arxiv_id} | Get a single paper |
| http://localhost:8000/api/v1/papers/search?q=... | BM25 keyword search |
| http://localhost:8000/docs | Interactive API docs (Swagger) |
| http://localhost:8080 | Airflow UI (admin / see .env) |
| http://localhost:6333/dashboard | Qdrant dashboard |

## arXiv Categories Ingested

- `q-bio.BM` — Biomolecules
- `q-bio.MN` — Molecular Networks
- `q-bio.GN` — Genomics

## Common Commands

```bash
make start    # build and start
make stop     # stop all services
make restart  # restart without rebuild
make logs     # stream logs
make health   # check service health
```
