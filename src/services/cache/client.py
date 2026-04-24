import hashlib
import json
import logging
from datetime import timedelta

import redis

from src.config import RedisSettings
from src.schemas.api.ask import AskRequest, AskResponse

logger = logging.getLogger(__name__)


class CacheClient:
    def __init__(self, redis_client: redis.Redis, settings: RedisSettings):
        self.redis = redis_client
        self.ttl = timedelta(hours=settings.ttl_hours)

    def _cache_key(self, request: AskRequest) -> str:
        key_data = {
            "query": request.query,
            "model": request.model,
            "top_k": request.top_k,
            "use_hybrid": request.use_hybrid,
            "categories": sorted(request.categories) if request.categories else [],
        }
        key_hash = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:16]
        return f"ask:{key_hash}"

    async def find_cached_response(self, request: AskRequest) -> AskResponse | None:
        try:
            cached = self.redis.get(self._cache_key(request))
            if cached:
                return AskResponse(**json.loads(cached))
            return None
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    async def store_response(self, request: AskRequest, response: AskResponse) -> bool:
        try:
            return bool(
                self.redis.set(
                    self._cache_key(request),
                    response.model_dump_json(),
                    ex=self.ttl,
                )
            )
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            return False
