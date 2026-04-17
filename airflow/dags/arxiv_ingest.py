import logging
import os
from datetime import date, timedelta

import pendulum
from airflow.sdk import dag, task

from src.db.session import get_session, make_engine, make_session_factory
from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import PaperCreate
from src.services.arxiv_client import fetch_papers
from src.services.qdrant_client import QdrantService

logger = logging.getLogger(__name__)


@dag(
    dag_id="arxiv_ingest",
    description="Daily pipeline: fetch q-bio papers from arXiv → store metadata in PostgreSQL",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="0 6 * * *",  # every day at 6 AM UTC
    catchup=False,
    max_active_runs=1,
    tags=["arxiv", "biochem", "ingestion"],
)
def arxiv_ingest():

    @task
    def fetch_and_store(ds: str | None = None):
        """
        Fetch yesterday's papers from arXiv and store them in PostgreSQL.
        ds is the DAG run date string (YYYY-MM-DD), injected by Airflow on
        scheduled runs. Manual triggers don't have a logical_date, so ds
        will be None — we fall back to today's date.
        """
        run_date = date.fromisoformat(ds) if ds else date.today()
        from_date = run_date - timedelta(days=1)
        to_date = run_date

        logger.info(f"Fetching papers from {from_date} to {to_date}")
        papers = fetch_papers(from_date=from_date, to_date=to_date)

        engine = make_engine(os.environ["DATABASE_URL"])
        session_factory = make_session_factory(engine)
        qdrant = QdrantService(url=os.environ["QDRANT_URL"])
        qdrant.setup_collection()

        inserted = 0
        skipped = 0

        with get_session(session_factory) as session:
            repo = PaperRepository(session)
            for p in papers:
                paper_create = PaperCreate(
                    arxiv_id=p.arxiv_id,
                    title=p.title,
                    authors=p.authors,
                    abstract=p.abstract,
                    categories=p.categories,
                    published_date=p.published_date,
                    pdf_url=p.pdf_url,
                )
                existing = repo.get_by_arxiv_id(p.arxiv_id)
                if existing:
                    skipped += 1
                    continue
                db_paper = repo.create(paper_create)
                qdrant.index_paper(db_paper)
                inserted += 1

        logger.info(f"Done — inserted: {inserted}, skipped (already exists): {skipped}")

    fetch_and_store()


arxiv_ingest()
