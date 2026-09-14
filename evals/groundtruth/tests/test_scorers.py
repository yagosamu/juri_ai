import math

import pytest

from evals.groundtruth.scorers import (Span, aggregate, hits_per_rank, is_hit, mrr, ndcg_at_k,
                                       overlap_ratio, recall_at_k, score_item)

P = Span("cpc", 100, 200)


def test_span_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        Span("cpc", -1, 10)
    with pytest.raises(ValueError):
        Span("cpc", 10, 10)
    with pytest.raises(ValueError):
        Span("cpc", 10, 5)


def test_overlap_ratio_is_fraction_of_passage_covered():
    assert overlap_ratio(Span("cpc", 150, 400), P) == 0.5
    assert overlap_ratio(Span("cpc", 0, 100), P) == 0.0
    assert overlap_ratio(Span("clt", 100, 200), P) == 0.0
    assert overlap_ratio(Span("cpc", 0, 1000), P) == 1.0


def test_is_hit_uses_half_coverage_threshold():
    assert is_hit(Span("cpc", 150, 400), P)
    assert not is_hit(Span("cpc", 151, 400), P)


def test_hits_credit_each_passage_once():
    retrieved = [Span("cpc", 0, 50), Span("cpc", 90, 210), Span("cpc", 100, 200)]
    assert hits_per_rank(retrieved, [P]) == [False, True, False]


def test_one_chunk_can_credit_two_different_passages():
    passages = [Span("cpc", 0, 100), Span("cpc", 100, 200)]
    retrieved = [Span("cpc", 0, 200)]
    assert recall_at_k(retrieved, passages, 10) == 1.0


def test_overlapping_chunks_over_one_passage_still_credit_once():
    retrieved = [Span("cpc", 100, 200), Span("cpc", 120, 220), Span("cpc", 140, 240)]
    assert hits_per_rank(retrieved, [P]) == [True, False, False]
    assert recall_at_k(retrieved, [P], 10) == 1.0
    assert mrr(retrieved, [P]) == 1.0


def test_recall_mrr_ndcg_single_passage():
    retrieved = [Span("cpc", 0, 50), Span("cpc", 90, 210)]
    assert recall_at_k(retrieved, [P], 1) == 0.0
    assert recall_at_k(retrieved, [P], 2) == 1.0
    assert mrr(retrieved, [P]) == 0.5
    assert math.isclose(ndcg_at_k(retrieved, [P], 10), 1 / math.log2(3))


def test_recall_two_passages_partial():
    passages = [P, Span("clt", 0, 100)]
    retrieved = [Span("clt", 0, 100)]
    assert recall_at_k(retrieved, passages, 10) == 0.5
    assert mrr(retrieved, passages) == 1.0


def test_no_hits_gives_zero():
    assert score_item([Span("cpc", 0, 10)], [P]) == {
        "recall@1": 0.0, "recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0, "ndcg@10": 0.0}


def test_aggregate_means_overall_and_by_category():
    rows = [
        {"category": "conceito", "recall@10": 1.0, "mrr": 1.0},
        {"category": "conceito", "recall@10": 0.0, "mrr": 0.0},
        {"category": "procedimento", "recall@10": 1.0, "mrr": 0.5},
    ]
    agg = aggregate(rows)
    assert agg["overall"]["recall@10"] == 2 / 3
    assert agg["by_category"]["conceito"]["recall@10"] == 0.5
    assert agg["by_category"]["procedimento"]["mrr"] == 0.5
    assert agg["by_category"]["conceito"]["n"] == 2


def test_aggregate_is_order_independent_with_heterogeneous_rows():
    rows_a = [
        {"category": "x", "mrr": 1.0},
        {"category": "x", "recall@10": 0.0, "mrr": 0.0},
    ]
    rows_b = list(reversed(rows_a))

    agg_a = aggregate(rows_a)["by_category"]["x"]
    agg_b = aggregate(rows_b)["by_category"]["x"]

    assert agg_a == agg_b == {"recall@10": 0.0, "mrr": 0.5, "n": 2}
