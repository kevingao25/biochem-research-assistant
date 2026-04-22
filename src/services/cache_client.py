import hashlib
import json
import logging
from datetime import timedelta
from typing import Optional

import redis.asyncio as aioredis

from src.schemas.api.ask import AskRequest, AskResponse

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24


class CacheClient:
    """Redis-based exact-match cache for /ask responses.

    Hashes the full request (query + model + settings) into a key so that
    identical requests are served instantly without re-running the RAG pipeline.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.ttl = timedelta(hours=CACHE_TTL_HOURS)

    def _cache_key(self, request: AskRequest) -> str:
        """Deterministic key from all request fields that affect the answer."""
        key_data = {
            "query": request.query,
            "model": request.model,
            "top_k": request.top_k,
            "use_hybrid": request.use_hybrid,
            "categories": sorted(request.categories) if request.categories else [],
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"ask:{key_hash}"

    async def get(self, request: AskRequest) -> Optional[AskResponse]:
        """Return cached response if one exists, None otherwise."""
        try:
            cached = await self.redis.get(self._cache_key(request))
            if cached:
                logger.info("Cache hit")
                return AskResponse(**json.loads(cached))
            return None
        except Exception as e:
            logger.warning(f"Cache read failed, skipping: {e}")
            return None

    async def set(self, request: AskRequest, response: AskResponse) -> None:
        """Store a response. Silently skips if Redis is unreachable."""
        try:
            await self.redis.set(
                self._cache_key(request),
                response.model_dump_json(),
                ex=self.ttl,
            )
        except Exception as e:
            logger.warning(f"Cache write failed, skipping: {e}")
