"""Semantic cache: thresholds, doc-filter keying, KB-version invalidation,
eviction, and pipeline integration (hit skips the LLM, rag answers get stored)."""

from typing import Any

import pytest

import core.chat_pipeline as pipeline
from core.chat_pipeline import chat_once, chat_stream
from core.config import settings
from core.retrieval import RetrievedChunk
from core.semcache import SemanticCache
from core.sessions import SessionStore
from tests.test_chat_pipeline import FakeResponse, make_chunk
from tests.test_sessions import FakeRedis


def make_cache() -> SemanticCache:
    return SemanticCache(FakeRedis())  # type: ignore[arg-type]


def make_store() -> SessionStore:
    return SessionStore(FakeRedis())  # type: ignore[arg-type]


SOURCE = {"tag": "S1", "filename": "oracle.pdf", "page": 212, "section": "", "snippet": ""}


async def test_hit_above_threshold() -> None:
    cache = make_cache()
    await cache.store([1.0, 0.0], "bidding thresholds", None, "cached answer", [SOURCE])
    hit = await cache.lookup([1.0, 0.0], None)
    assert hit is not None
    assert hit["answer"] == "cached answer"
    assert hit["sources"][0]["tag"] == "S1"


async def test_miss_below_threshold() -> None:
    cache = make_cache()
    await cache.store([1.0, 0.0], "q", None, "a", [])
    assert await cache.lookup([0.0, 1.0], None) is None  # orthogonal → sim 0


async def test_doc_filter_is_part_of_the_key() -> None:
    cache = make_cache()
    await cache.store([1.0, 0.0], "q", "policy.pdf", "filtered answer", [])
    # a filtered answer must never serve an unfiltered question (or vice versa)
    assert await cache.lookup([1.0, 0.0], None) is None
    hit = await cache.lookup([1.0, 0.0], "policy.pdf")
    assert hit is not None and hit["answer"] == "filtered answer"


async def test_kb_version_bump_invalidates_everything() -> None:
    cache = make_cache()
    await cache.store([1.0, 0.0], "q", None, "a", [])
    await cache.bump_kb_version()  # simulates ingest/delete
    assert await cache.lookup([1.0, 0.0], None) is None


async def test_eviction_caps_entry_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "semcache_max_entries", 2)
    cache = make_cache()
    for i in range(3):
        await cache.store([1.0, 0.0], f"q{i}", None, f"a{i}", [])
    assert await cache._redis.hlen("semcache:0") == 2


async def test_disabled_flag_bypasses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "semcache_enabled", False)
    cache = make_cache()
    await cache.store([1.0, 0.0], "q", None, "a", [])
    assert await cache.lookup([1.0, 0.0], None) is None


# ---- pipeline integration ----


async def test_chat_once_cache_hit_skips_llm_and_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, cache = make_store(), make_cache()
    await cache.store([1.0, 0.0], "what is a purchase order?", None, "Cached [S1]", [SOURCE])

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0]]

    async def fail_complete(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("LLM must not be called on a cache hit")

    async def fail_retrieve(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("retrieval must not run on a cache hit")

    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)
    monkeypatch.setattr(pipeline, "complete", fail_complete)
    monkeypatch.setattr(pipeline, "retrieve", fail_retrieve)

    answer, sources = await chat_once(None, store, "s1", "what is a purchase order?", cache=cache)
    assert answer == "Cached [S1]"
    assert sources[0]["filename"] == "oracle.pdf"
    history = await store.history("s1")
    assert history is not None and len(history) == 2  # cached turn still persisted


async def test_chat_stream_cache_hit_yields_answer_and_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, cache = make_store(), make_cache()
    await cache.store([1.0, 0.0], "what is a purchase order?", None, "Cached [S1]", [SOURCE])

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0]]

    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)

    events = [
        e async for e in chat_stream(None, store, "s1", "what is a purchase order?", cache=cache)
    ]
    assert events[0] == {"delta": "Cached [S1]"}
    assert events[1]["sources"][0]["tag"] == "S1"


async def test_fresh_rag_answer_is_stored_in_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    store, cache = make_store(), make_cache()

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.0, 1.0]]

    async def fake_retrieve(index: Any, query: str, **kwargs: Any) -> list[RetrievedChunk]:
        assert kwargs.get("query_embedding") == [0.0, 1.0]  # embedded once, reused
        return [make_chunk()]

    async def fake_complete(role: str, messages: Any, **kwargs: Any) -> Any:
        return FakeResponse("Fresh answer [S1].")

    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)
    monkeypatch.setattr(pipeline, "retrieve", fake_retrieve)
    monkeypatch.setattr(pipeline, "complete", fake_complete)

    await chat_once(None, store, "s1", "a novel question?", cache=cache)
    hit = await cache.lookup([0.0, 1.0], None)
    assert hit is not None and hit["answer"] == "Fresh answer [S1]."


async def test_refusal_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    store, cache = make_store(), make_cache()

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.5, 0.5]]

    async def fake_retrieve(index: Any, query: str, **kwargs: Any) -> list[RetrievedChunk]:
        return []  # gate rejected everything

    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)
    monkeypatch.setattr(pipeline, "retrieve", fake_retrieve)

    await chat_once(None, store, "s1", "unknown topic?", cache=cache)
    assert await cache._redis.hlen("semcache:0") == 0
