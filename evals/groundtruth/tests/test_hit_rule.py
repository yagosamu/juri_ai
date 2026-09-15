"""Tests for the bidirectional hit rule (Ruling 1, 2026-09-14): a chunk hits a golden passage when
it covers at least 50% of the passage, or when at least 50% of the chunk lies inside the passage."""
from evals.groundtruth.scorers import Span, containment_ratio, is_hit, overlap_ratio, recall_at_k


def test_containment_ratio_fully_inside_is_one():
    passage = Span("cpc", 0, 3000)
    chunk = Span("cpc", 1000, 1800)
    assert containment_ratio(chunk, passage) == 1.0


def test_containment_ratio_half_inside_is_half():
    passage = Span("cpc", 100, 200)
    chunk = Span("cpc", 150, 250)
    assert containment_ratio(chunk, passage) == 0.5


def test_containment_ratio_different_doc_is_zero():
    passage = Span("cpc", 0, 100)
    chunk = Span("clt", 0, 100)
    assert containment_ratio(chunk, passage) == 0.0


def test_containment_ratio_disjoint_is_zero():
    passage = Span("cpc", 0, 100)
    chunk = Span("cpc", 200, 300)
    assert containment_ratio(chunk, passage) == 0.0


def test_chunk_fully_inside_long_passage_is_a_hit_via_containment():
    passage = Span("cpc", 0, 3000)
    chunk = Span("cpc", 1000, 1800)
    assert containment_ratio(chunk, passage) == 1.0
    assert not (chunk.end - chunk.start) / (passage.end - passage.start) >= 0.5  # covers under 50% of passage
    assert is_hit(chunk, passage)


def test_exactly_half_of_chunk_inside_is_a_hit():
    passage = Span("cpc", 100, 200)
    chunk = Span("cpc", 150, 250)
    assert containment_ratio(chunk, passage) == 0.5
    assert is_hit(chunk, passage)


def test_just_under_half_on_both_ratios_is_not_a_hit():
    passage = Span("cpc", 100, 200)
    chunk = Span("cpc", 151, 251)
    assert containment_ratio(chunk, passage) < 0.5
    assert not is_hit(chunk, passage)


def test_chunk_on_another_doc_id_is_never_a_hit():
    passage = Span("cpc", 0, 3000)
    chunk = Span("clt", 1000, 1800)
    assert not is_hit(chunk, passage)


def test_recall_at_k_credits_passage_found_only_through_containment():
    passage = Span("cpc", 0, 3000)
    chunk = Span("cpc", 1000, 1800)
    assert recall_at_k([chunk], [passage], 10) == 1.0


def test_containment_exactly_at_the_0_5_boundary_on_a_long_passage():
    """Isolates the containment boundary from the passage-coverage boundary: here passage coverage
    is only 0.1, far under the threshold, so a hit at exactly 0.5 containment can only come from the
    containment side of is_hit, not from overlap_ratio."""
    passage = Span("cpc", 0, 1000)
    hit_chunk = Span("cpc", 900, 1100)
    assert containment_ratio(hit_chunk, passage) == 0.5
    assert overlap_ratio(hit_chunk, passage) == 0.1
    assert is_hit(hit_chunk, passage)

    miss_chunk = Span("cpc", 901, 1101)
    assert containment_ratio(miss_chunk, passage) == 0.495
    assert not is_hit(miss_chunk, passage)
