import logging

import redis

from src.config import Settings
from src.services.cache.client import CacheClient

logger = logging.getLogger(__name__)


def make_redis_client(settings: Settings) -> redis.Redis:
    r = settings.redis
    client = redis.Redis.from_url(
        r.url,
        decode_responses=True,
        socket_timeout=30,
        socket_connect_timeout=30,
        retry_on_timeout=True,
    )
    client.ping()
    logger.info(f"Connected to Redis at {r.url}")
    return client


def make_cache_client(settings: Settings) -> CacheClient | None:
    try:
        redis_client = make_redis_client(settings)
    except redis.RedisError as e:
        logger.warning(f"Redis unavailable; response cache disabled: {e}")
        return None
    return CacheClient(redis_client, settings.redis)
