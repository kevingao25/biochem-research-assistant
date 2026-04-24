import logging
from datetime import date, timedelta

from src.db.factory import make_database
from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import PaperCreate
from src.services.arxiv.factory import make_arxiv_client

logger = logging.getLogger(__name__)


def fetch_papers(ds: str | None = None) -> dict:
    """Fetch yesterday's papers from arXiv and store metadata in PostgreSQL.

    ds is the DAG run date (YYYY-MM-DD) injected by Airflow on scheduled runs.
    Manual triggers don't set ds, so we fall back to today.
    """
    run_date = date.fromisoformat(ds) if ds else date.today()
    from_date = run_date - timedelta(days=1)
    to_date = run_date

    logger.info(f"Fetching papers from {from_date} to {to_date}")
    papers = make_arxiv_client().fetch_papers(from_date=from_date, to_date=to_date)

    db = make_database()

    inserted = 0
    skipped = 0

    with db.get_session() as session:
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
