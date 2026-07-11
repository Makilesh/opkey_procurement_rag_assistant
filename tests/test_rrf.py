from core.retrieval import rrf_fuse, select_with_document_diversity


def _cand(cid: str, filename: str, score: float):
    return ({"id": cid, "metadata": {"source_filename": filename}}, score)


def test_diversity_guard_swaps_in_second_document() -> None:
    passing = [
        _cand("a", "doc1.pdf", 0.9),
        _cand("b", "doc1.pdf", 0.8),
        _cand("c", "doc1.pdf", 0.7),
        _cand("d", "doc1.pdf", 0.6),
        _cand("e", "doc2.pdf", 0.5),  # second doc passed the gate too
    ]
    kept, diversified = select_with_document_diversity(passing, top_k=4)
    assert diversified is True
    files = [c["metadata"]["source_filename"] for c, _ in kept]
    assert files == ["doc1.pdf", "doc1.pdf", "doc1.pdf", "doc2.pdf"]


def test_diversity_guard_noop_when_single_document_passes() -> None:
    passing = [_cand(str(i), "doc1.pdf", 0.9 - i * 0.1) for i in range(6)]
    kept, diversified = select_with_document_diversity(passing, top_k=4)
    assert diversified is False
    assert [c["id"] for c, _ in kept] == ["0", "1", "2", "3"]


def test_diversity_guard_noop_when_both_docs_already_kept() -> None:
    passing = [
        _cand("a", "doc1.pdf", 0.9),
        _cand("b", "doc2.pdf", 0.8),
        _cand("c", "doc1.pdf", 0.7),
        _cand("d", "doc1.pdf", 0.6),
        _cand("e", "doc2.pdf", 0.5),
    ]
    kept, diversified = select_with_document_diversity(passing, top_k=4)
    assert diversified is False
    assert [c["id"] for c, _ in kept] == ["a", "b", "c", "d"]


def test_diversity_guard_fewer_than_top_k() -> None:
    passing = [_cand("a", "doc1.pdf", 0.9)]
    kept, diversified = select_with_document_diversity(passing, top_k=4)
    assert diversified is False
    assert len(kept) == 1


def test_rrf_agreement_wins() -> None:
    # "b" is ranked well by both lists; "a" and "c" only by one each.
    fused = rrf_fuse([["a", "b", "c"], ["b", "d", "a"]], k=60)
    assert fused[0] == "b"
    assert set(fused) == {"a", "b", "c", "d"}


def test_rrf_dedup() -> None:
    fused = rrf_fuse([["a", "b"], ["a", "b"]], k=60)
    assert fused == ["a", "b"]
    assert len(fused) == len(set(fused))


def test_rrf_rank_order_within_single_list() -> None:
    fused = rrf_fuse([["x", "y", "z"]], k=60)
    assert fused == ["x", "y", "z"]


def test_rrf_top_of_one_list_beats_tail_of_both() -> None:
    # "top" is #1 in list one and absent from list two; "mid" is low in both.
    fused = rrf_fuse([["top", "f1", "f2", "f3", "mid"], ["f4", "f5", "f6", "f7", "mid"]], k=60)
    assert fused.index("top") < fused.index("f2")


def test_rrf_empty_lists() -> None:
    assert rrf_fuse([[], []], k=60) == []
