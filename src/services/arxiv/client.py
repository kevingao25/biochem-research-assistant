import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import arxiv

logger = logging.getLogger(__name__)

# arXiv categories relevant to phage-bacteria research
CATEGORIES = ["q-bio.BM", "q-bio.MN", "q-bio.GN"]


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: datetime
    pdf_url: str


def fetch_papers(from_date: date, to_date: date, max_results: int = 100) -> list[ArxivPaper]:
    """
    Fetch papers from arXiv published between from_date and to_date.

    arXiv date format: YYYYMMDDHHMMSS
    We search all three q-bio categories with OR and filter by date range.
    The client adds a 3-second delay between requests automatically.
    """
    category_query = " OR ".join(f"cat:{c}" for c in CATEGORIES)
    date_from = from_date.strftime("%Y%m%d") + "0000"
    date_to = to_date.strftime("%Y%m%d") + "2359"
    query = f"({category_query}) AND submittedDate:[{date_from} TO {date_to}]"

    logger.info(f"Fetching arXiv papers: {query}")

    client = arxiv.Client(
        page_size=50,
        delay_seconds=3.0,  # arXiv rate limit: 3 seconds between requests
        num_retries=3,
    )

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    for result in client.results(search):
        papers.append(
            ArxivPaper(
                arxiv_id=result.entry_id.split("/")[-1],
                title=result.title.replace("\n", " ").strip(),
                authors=[a.name for a in result.authors],
                abstract=result.summary.replace("\n", " ").strip(),
                categories=[c for c in result.categories],
                published_date=result.published.replace(tzinfo=timezone.utc)
                if result.published.tzinfo is None
                else result.published,
                pdf_url=result.pdf_url or "",
            )
        )

    logger.info(f"Fetched {len(papers)} papers")
    return papers
