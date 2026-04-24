import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

import arxiv

from src.config import ArxivSettings

logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_date: datetime
    pdf_url: str


class ArxivClient:
    """Fetches paper metadata from the arXiv API."""

    def __init__(self, settings: ArxivSettings):
        self.settings = settings
        self._client = arxiv.Client(
            page_size=50,
            delay_seconds=settings.rate_limit_delay,
            num_retries=3,
        )

    def fetch_papers(self, from_date: date, to_date: date, max_results: int | None = None) -> list[ArxivPaper]:
        """Fetch papers published between from_date and to_date across configured categories."""
        max_results = max_results or self.settings.max_results
        category_query = " OR ".join(f"cat:{c}" for c in self.settings.search_categories)
        date_from = from_date.strftime("%Y%m%d") + "0000"
        date_to = to_date.strftime("%Y%m%d") + "2359"
        query = f"({category_query}) AND submittedDate:[{date_from} TO {date_to}]"

        logger.info(f"Fetching arXiv papers: {query}")

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        papers = []
        for result in self._client.results(search):
            papers.append(
                ArxivPaper(
                    arxiv_id=result.entry_id.split("/")[-1],
                    title=result.title.replace("\n", " ").strip(),
                    authors=[a.name for a in result.authors],
                    abstract=result.summary.replace("\n", " ").strip(),
                    categories=list(result.categories),
                    published_date=result.published.replace(tzinfo=UTC)
                    if result.published.tzinfo is None
                    else result.published,
                    pdf_url=result.pdf_url or "",
                )
            )

        logger.info(f"Fetched {len(papers)} papers")
        return papers
