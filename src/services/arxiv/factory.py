from src.services.arxiv.client import fetch_papers

# fetch_papers is a standalone function; expose it directly for convenience.
make_arxiv_client = fetch_papers
