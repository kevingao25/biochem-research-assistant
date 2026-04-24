from src.config import get_settings
from src.services.jina.client import JinaClient


def make_jina_client() -> JinaClient:
    settings = get_settings()
    return JinaClient(api_key=settings.jina_api_key)
