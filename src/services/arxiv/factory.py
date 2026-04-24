from src.config import get_settings
from src.services.arxiv.client import ArxivClient


def make_arxiv_client() -> ArxivClient:
    settings = get_settings()
    return ArxivClient(settings=settings.arxiv)
