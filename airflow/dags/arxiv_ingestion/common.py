import logging
import sys
from functools import lru_cache
from typing import Any, Tuple

sys.path.insert(0, "/opt/airflow")

from src.config import get_settings
from src.db.factory import make_database
from src.services.arxiv.factory import make_arxiv_client
from src.services.jina.factory import make_jina_client
from src.services.pdf_parser.factory import make_pdf_parser_service
from src.services.qdrant.factory import make_qdrant_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_cached_services() -> Tuple[Any, Any, Any, Any, Any]:
    """Cached service instances shared across DAG tasks in the same worker process."""
    logger.info("Initializing DAG services")
    arxiv_client = make_arxiv_client()
    pdf_parser = make_pdf_parser_service()
    database = make_database()
    qdrant_client = make_qdrant_client()
    jina_client = make_jina_client()
    logger.info("DAG services ready")
    return arxiv_client, pdf_parser, database, qdrant_client, jina_client
