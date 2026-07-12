"""Document-filter retrieval: dense + sparse legs restrict to the chosen file,
and the pipeline threads the filter through to retrieval."""

from typing import Any

import pytest

import core.chat_pipeline as pipeline
from core.chat_pipeline import prepare_turn
from core.config import settings
from core.index import IndexStore
from core.retrieval import RetrievedChunk
from core.sessions import SessionStore
from tests.test_chat_pipeline import make_chunk
from tests.test_sessions import FakeRedis


@pytest.fixture()
def index(tmp_path, monkeypatch: pytest.MonkeyPatch) -> IndexStore:
    """Embedded-Chroma index with two tiny docs and hand-made embeddings —
    no model download, no network."""
    monkeypatch.setattr(settings, "chroma_dir", str(tmp_path / "chroma"))
    monkeypatch.setattr(settings, "bm25_path", str(tmp_path / "chroma" / "bm25.pkl"))
    store = IndexStore()
    # 3 docs so the query terms get positive BM25 idf (with N=2 and df=N,
    # rank_bm25 yields non-positive scores and sparse search returns nothing).
    store._collection.upsert(
        ids=["d1:0", "d2:0", "d3:0"],
        embeddings=[[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]],
        documents=[
            "bravo threshold rules",
            "charlie threshold rules",
            "delta echo foxtrot unrelated filler",
        ],
        metadatas=[
            {"doc_id": "d1", "source_filename": "a.pdf", "page_start": 1,
             "page_end": 1, "chunk_index": 0, "section_path": ""},
            {"doc_id": "d2", "source_filename": "b.pdf", "page_start": 1,
             "page_end": 1, "chunk_index": 0, "section_path": ""},
            {"doc_id": "d3", "source_filename": "c.pdf", "page_start": 1,
             "page_end": 1, "chunk_index": 0, "section_path": ""},
        ],
    )
    store._registry = {
        "d1": {"filename": "a.pdf", "pages": 1, "chunks": 1, "ingested_at": "t1"},
        "d2": {"filename": "b.pdf", "pages": 1, "chunks": 1, "ingested_at": "t2"},
        "d3": {"filename": "c.pdf", "pages": 1, "chunks": 1, "ingested_at": "t3"},
    }
    store._rebuild_bm25_sync()
    return store


def test_sparse_search_respects_filter(index: IndexStore) -> None:
    unfiltered = index.sparse_search_sync("bravo charlie", 5)
    assert {c["metadata"]["source_filename"] for c in unfiltered} == {"a.pdf", "b.pdf"}

    filtered = index.sparse_search_sync("bravo charlie", 5, filenames=["b.pdf"])
    assert filtered, "filter must not starve results that exist in the allowed doc"
    assert {c["metadata"]["source_filename"] for c in filtered} == {"b.pdf"}


def test_dense_search_respects_filter(index: IndexStore) -> None:
    # query vector points at d1/a.pdf — but the filter forces b.pdf
    filtered = index.dense_search_sync([1.0, 0.0], 5, filenames=["b.pdf"])
    assert filtered
    assert {c["metadata"]["source_filename"] for c in filtered} == {"b.pdf"}


async def test_prepare_turn_passes_doc_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_retrieve(index: Any, query: str, **kwargs: Any) -> list[RetrievedChunk]:
        captured.update(kwargs)
        return [make_chunk()]

    monkeypatch.setattr(pipeline, "retrieve", fake_retrieve)
    store = SessionStore(FakeRedis())  # type: ignore[arg-type]

    prepared = await prepare_turn(None, store, "s1", "what is a PO?", doc_filter="a.pdf")
    assert captured["filenames"] == ["a.pdf"]
    assert prepared.doc_filter == "a.pdf"

    captured.clear()
    await prepare_turn(None, store, "s2", "what is a PO?")
    assert captured["filenames"] is None  # no filter → search everything
