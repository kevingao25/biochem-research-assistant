from unittest.mock import MagicMock

import pytest

from src.schemas.api.ask import AskRequest
from src.services.cache_client import CacheClient


@pytest.fixture
def cache():
    # Redis client is not used by _cache_key — mock it so we can construct CacheClient
    return CacheClient(redis_client=MagicMock())


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
        r1 = make_request()
        r2 = make_request()
        assert cache._cache_key(r1) == cache._cache_key(r2)

    def test_different_query_produces_different_key(self, cache):
        r1 = make_request(query="What is CRISPR?")
        r2 = make_request(query="How do phages work?")
        assert cache._cache_key(r1) != cache._cache_key(r2)

    def test_different_model_produces_different_key(self, cache):
        r1 = make_request(model="llama3.2:1b")
        r2 = make_request(model="mistral:7b")
        assert cache._cache_key(r1) != cache._cache_key(r2)

    def test_different_top_k_produces_different_key(self, cache):
        r1 = make_request(top_k=3)
        r2 = make_request(top_k=10)
        assert cache._cache_key(r1) != cache._cache_key(r2)

    def test_different_use_hybrid_produces_different_key(self, cache):
        r1 = make_request(use_hybrid=True)
        r2 = make_request(use_hybrid=False)
        assert cache._cache_key(r1) != cache._cache_key(r2)

    def test_categories_order_does_not_affect_key(self, cache):
        # Same categories in different order must produce the same key
        r1 = make_request(categories=["q-bio.BM", "q-bio.GN"])
        r2 = make_request(categories=["q-bio.GN", "q-bio.BM"])
        assert cache._cache_key(r1) == cache._cache_key(r2)

    def test_key_has_correct_prefix(self, cache):
        key = cache._cache_key(make_request())
        assert key.startswith("ask:")

    def test_key_is_fixed_length(self, cache):
        # prefix "ask:" (4) + 16-char hash = 20 chars total
        key = cache._cache_key(make_request())
        assert len(key) == 20
