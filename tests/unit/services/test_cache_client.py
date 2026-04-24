from unittest.mock import MagicMock

import pytest

from src.config import RedisSettings
from src.schemas.api.ask import AskRequest
from src.services.cache.client import CacheClient


@pytest.fixture
def cache():
    return CacheClient(redis_client=MagicMock(), settings=RedisSettings())


def make_request(**overrides) -> AskRequest:
    defaults = {
        "query": "What is CRISPR?",
        "model": "llama3.2:1b",
        "top_k": 5,
        "use_hybrid": True,
        "categories": None,
    }
    return AskRequest(**{**defaults, **overrides})


class TestCacheKey:
    def test_same_request_produces_same_key(self, cache):
        assert cache._cache_key(make_request()) == cache._cache_key(make_request())

    def test_different_query_produces_different_key(self, cache):
        assert cache._cache_key(make_request(query="What is CRISPR?")) != cache._cache_key(make_request(query="How do phages work?"))

    def test_different_model_produces_different_key(self, cache):
        assert cache._cache_key(make_request(model="llama3.2:1b")) != cache._cache_key(make_request(model="mistral:7b"))

    def test_different_top_k_produces_different_key(self, cache):
        assert cache._cache_key(make_request(top_k=3)) != cache._cache_key(make_request(top_k=10))

    def test_different_use_hybrid_produces_different_key(self, cache):
        assert cache._cache_key(make_request(use_hybrid=True)) != cache._cache_key(make_request(use_hybrid=False))

    def test_categories_order_does_not_affect_key(self, cache):
        r1 = make_request(categories=["q-bio.BM", "q-bio.GN"])
        r2 = make_request(categories=["q-bio.GN", "q-bio.BM"])
        assert cache._cache_key(r1) == cache._cache_key(r2)

    def test_key_has_correct_prefix(self, cache):
        assert cache._cache_key(make_request()).startswith("ask:")

    def test_key_is_fixed_length(self, cache):
        assert len(cache._cache_key(make_request())) == 20
