import logging
import os
from datetime import date, timedelta
from datetime import datetime, timezone

import pendulum
from airflow.sdk import dag, task

from src.db.session import get_session, make_engine, make_session_factory
from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import PaperCreate
from src.services.arxiv_client import fetch_papers
from src.services.chunker import TextChunker
from src.services.pdf_processor import PdfProcessor
from src.services.qdrant_client import QdrantService

logger = logging.getLogger(__name__)

PDF_BATCH_SIZE = 50   # max papers to process per daily run


@dag(
    dag_id="arxiv_ingest",
    description="Daily pipeline: fetch q-bio papers → store in PostgreSQL → parse PDFs → index chunks in Qdrant",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["arxiv", "biochem", "ingestion"],
)
def arxiv_ingest():

    @task
    def fetch_and_store(ds: str | None = None):
        """Fetch yesterday's papers from arXiv and store metadata in PostgreSQL.

        ds is the DAG run date (YYYY-MM-DD) injected by Airflow on scheduled runs.
        Manual triggers don't set ds, so we fall back to today.
        """
        run_date = date.fromisoformat(ds) if ds else date.today()
        from_date = run_date - timedelta(days=1)
        to_date = run_date

        logger.info(f"Fetching papers from {from_date} to {to_date}")
        papers = fetch_papers(from_date=from_date, to_date=to_date)

        engine = make_engine(os.environ["DATABASE_URL"])
        session_factory = make_session_factory(engine)

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
                repo.create(paper_create)
                inserted += 1

        logger.info(f"Done — inserted: {inserted}, skipped (already exists): {skipped}")
        return {"inserted": inserted, "skipped": skipped}

    @task
    def process_and_index():
        """Download PDFs for unprocessed papers, parse with docling, chunk, and index into Qdrant.

        Processes up to PDF_BATCH_SIZE papers per run. Papers that fail PDF processing
        remain pdf_processed=False and are retried on the next daily run.
        """
        engine = make_engine(os.environ["DATABASE_URL"])
        session_factory = make_session_factory(engine)
        qdrant = QdrantService(url=os.environ["QDRANT_URL"])
        qdrant.setup_collection()

        processor = PdfProcessor()
        chunker = TextChunker()

        processed = 0
        failed = 0

        with get_session(session_factory) as session:
            repo = PaperRepository(session)
            papers = repo.get_unprocessed(limit=PDF_BATCH_SIZE)

            logger.info(f"Processing {len(papers)} unprocessed papers")

            for paper in papers:
                pdf_content = processor.process(paper.arxiv_id, paper.pdf_url)

                if pdf_content is None:
                    # process() already logged the error; leave pdf_processed=False for retry
                    failed += 1
                    continue

                # Persist extracted text to Postgres
                paper.raw_text = pdf_content.raw_text
                paper.sections = [{"title": s.title, "content": s.content} for s in pdf_content.sections]
                paper.parser_used = "docling"
                paper.parser_metadata = pdf_content.parser_metadata
                paper.pdf_processed = True
                paper.pdf_processing_date = datetime.now(timezone.utc)
                repo.update(paper)

                # Chunk and index into Qdrant
                chunks = chunker.chunk_paper(
                    title=paper.title,
                    abstract=paper.abstract,
                    arxiv_id=paper.arxiv_id,
                    paper_id=str(paper.id),
                    sections=pdf_content.sections,
                    raw_text=pdf_content.raw_text,
                )

                if chunks:
                    qdrant.index_chunks(chunks)

                processed += 1
                logger.info(f"Processed {paper.arxiv_id}: {len(chunks)} chunks indexed")

        logger.info(f"Batch complete — processed: {processed}, failed: {failed}")
        return {"processed": processed, "failed": failed}

    t1 = fetch_and_store()
    t2 = process_and_index()
    t1 >> t2


arxiv_ingest()
