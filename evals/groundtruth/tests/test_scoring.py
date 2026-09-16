import pytest

from evals.groundtruth.generation.scoring import (aggregate_faithfulness_relevancy, reconcile_scored_golden,
                                                   score_golden_answers)


class FakeTestCase:
    def __init__(self, input, actual_output, retrieval_context):
        self.input = input
        self.actual_output = actual_output
        self.retrieval_context = retrieval_context


class FakeMetric:
    """score is 1.0 when it was handed a retrieval_context, else 0.0. Records what it measured."""

    instances = []

    def __init__(self, threshold, model, include_reason):
        self.threshold, self.model, self.include_reason = threshold, model, include_reason
        self.score = None
        self.reason = None
        self.evaluation_cost = 0.001
        self.measured = None
        FakeMetric.instances.append(self)

    def measure(self, test_case):
        self.measured = test_case
        self.score = 1.0 if test_case.retrieval_context else 0.0
        self.reason = "fake reason"


def _rows():
    return [
        {"id": "g-01", "question": "q1", "category": "conceito", "answer": "a1", "contexts": ["ctx1"],
         "searched": True, "run_failed": False},
        {"id": "g-02", "question": "q2", "category": "conceito", "answer": "a2", "contexts": [], "searched": False,
         "run_failed": False},
        {"id": "g-03", "question": "q3", "category": "fato_pontual", "answer": "a3", "contexts": ["ctx3"],
         "searched": True, "run_failed": False},
    ]


def test_score_golden_answers_uses_injected_fakes_and_never_imports_deepeval():
    FakeMetric.instances.clear()
    results = score_golden_answers(_rows(), faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    assert len(results) == 3
    faithfulness_measured = sum(1 for r in results if r["faithfulness_score"] is not None)
    assert faithfulness_measured == 2
    assert results[1]["no_retrieval"] is True
    assert results[1]["faithfulness_score"] is None
    assert results[1]["relevancy_score"] is not None  # still scored


def test_score_golden_answers_never_passes_a_placeholder_context_for_no_retrieval():
    FakeMetric.instances.clear()
    score_golden_answers(_rows(), faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric, test_case_cls=FakeTestCase)
    no_retrieval_case = [m.measured for m in FakeMetric.instances if m.measured.actual_output == "a2"][0]
    assert no_retrieval_case.retrieval_context is None


def test_score_golden_answers_passes_the_model_through_to_the_metrics():
    FakeMetric.instances.clear()
    score_golden_answers(_rows(), model="gpt-4.1-mini", faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                         test_case_cls=FakeTestCase)
    assert all(m.model == "gpt-4.1-mini" for m in FakeMetric.instances)


def test_score_golden_answers_records_evaluation_cost_when_present():
    FakeMetric.instances.clear()
    results = score_golden_answers(_rows(), faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    assert results[0]["relevancy_cost"] == 0.001
    assert results[0]["faithfulness_cost"] == 0.001


def test_aggregate_faithfulness_relevancy_excludes_no_retrieval_from_faithfulness_mean():
    results = [
        {"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
         "relevancy_score": 0.9},
        {"id": "g-02", "category": "conceito", "no_retrieval": True, "faithfulness_score": None,
         "relevancy_score": 0.5},
        {"id": "g-03", "category": "fato_pontual", "no_retrieval": False, "faithfulness_score": 0.6,
         "relevancy_score": 0.7},
    ]
    agg = aggregate_faithfulness_relevancy(results)
    assert agg["no_retrieval"] == 1
    assert agg["overall"]["faithfulness"]["n"] == 2
    assert agg["overall"]["faithfulness"]["mean"] == pytest.approx(0.7)
    assert agg["overall"]["relevancy"]["n"] == 3
    assert agg["by_category"]["conceito"]["faithfulness"]["n"] == 1
    assert agg["by_category"]["conceito"]["relevancy"]["n"] == 2


def test_aggregate_handles_a_category_with_only_no_retrieval_rows():
    results = [{"id": "g-01", "category": "procedimento", "no_retrieval": True, "faithfulness_score": None,
               "relevancy_score": 0.4}]
    agg = aggregate_faithfulness_relevancy(results)
    assert agg["by_category"]["procedimento"]["faithfulness"]["n"] == 0
    assert agg["by_category"]["procedimento"]["faithfulness"]["mean"] is None


def test_aggregate_handles_empty_results():
    agg = aggregate_faithfulness_relevancy([])
    assert agg["no_retrieval"] == 0
    assert agg["overall"]["faithfulness"] == {"mean": None, "n": 0}
    assert agg["by_category"] == {}


# --- Fix round 1: failed runs --------------------------------------------------------

def _failed_row():
    return {"id": "oos-01", "question": "q", "category": "fora_de_escopo", "answer": "rate limit error text",
           "contexts": [], "searched": False, "run_failed": True}


def test_score_golden_answers_never_calls_deepeval_for_a_failed_run():
    FakeMetric.instances.clear()
    rows = _rows() + [{**_failed_row(), "id": "g-04", "category": "conceito"}]
    results = score_golden_answers(rows, faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    failed = next(r for r in results if r["id"] == "g-04")
    assert failed["run_failed"] is True
    assert failed["relevancy_score"] is None
    assert failed["faithfulness_score"] is None
    # only the 3 non-failed rows from _rows() triggered a relevancy measurement
    assert len(FakeMetric.instances) == 2 + 3  # 3 relevancy + 2 faithfulness (g-02 has no_retrieval)


def test_score_golden_answers_marks_a_completed_row_run_failed_false():
    FakeMetric.instances.clear()
    results = score_golden_answers(_rows(), faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    assert all(r["run_failed"] is False for r in results)


def test_aggregate_excludes_run_failed_from_both_means_and_counts_it_separately():
    results = [
        {"id": "g-01", "category": "conceito", "run_failed": False, "no_retrieval": False,
         "faithfulness_score": 0.8, "relevancy_score": 0.9},
        {"id": "g-02", "category": "conceito", "run_failed": True, "no_retrieval": False,
         "faithfulness_score": None, "relevancy_score": None},
    ]
    agg = aggregate_faithfulness_relevancy(results)
    assert agg["run_failed"] == 1
    assert agg["overall"]["faithfulness"]["n"] == 1
    assert agg["overall"]["relevancy"]["n"] == 1
    assert agg["by_category"]["conceito"]["relevancy"]["n"] == 1


def test_reconcile_scored_golden_keeps_a_non_failed_rows_stored_score():
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": False}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "faithfulness_reason": "ok", "faithfulness_cost": 0.001, "relevancy_score": 0.9,
              "relevancy_reason": "ok", "relevancy_cost": 0.001}]
    out = reconcile_scored_golden(golden_rows, stored)
    assert out[0]["faithfulness_score"] == 0.8
    assert out[0]["run_failed"] is False


def test_reconcile_scored_golden_ignores_a_stored_verdict_on_a_failed_row():
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": True}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "faithfulness_reason": "stale, must be ignored", "faithfulness_cost": 0.001,
              "relevancy_score": 0.9, "relevancy_reason": "stale, must be ignored", "relevancy_cost": 0.001}]
    out = reconcile_scored_golden(golden_rows, stored)
    assert out[0]["run_failed"] is True
    assert out[0]["faithfulness_score"] is None
    assert out[0]["relevancy_score"] is None


def test_reconcile_scored_golden_raises_when_a_non_failed_row_has_no_stored_score():
    golden_rows = [{"id": "g-99", "category": "conceito", "run_failed": False}]
    with pytest.raises(ValueError):
        reconcile_scored_golden(golden_rows, stored_scored=[])


# --- Fix round 2: answer_sha256 tripwire ------------------------------------------

def test_score_golden_answers_writes_answer_sha256_on_a_completed_row():
    from evals.groundtruth.generation.answers import answer_sha256
    FakeMetric.instances.clear()
    results = score_golden_answers(_rows(), faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    assert results[0]["answer_sha256"] == answer_sha256("a1")


def test_score_golden_answers_writes_answer_sha256_on_a_failed_row():
    from evals.groundtruth.generation.answers import answer_sha256
    FakeMetric.instances.clear()
    rows = [{"id": "g-04", "question": "q", "category": "conceito", "answer": "rate limit error",
            "run_failed": True}]
    results = score_golden_answers(rows, faithfulness_cls=FakeMetric, relevancy_cls=FakeMetric,
                                   test_case_cls=FakeTestCase)
    assert results[0]["answer_sha256"] == answer_sha256("rate limit error")


def test_reconcile_scored_golden_raises_when_the_stored_hash_does_not_match_the_current_answer():
    from evals.groundtruth.generation.answers import answer_sha256
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": False, "answer": "new answer text"}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "relevancy_score": 0.9, "answer_sha256": answer_sha256("a different, older answer text")}]
    with pytest.raises(ValueError):
        reconcile_scored_golden(golden_rows, stored)


def test_reconcile_scored_golden_accepts_a_matching_hash():
    from evals.groundtruth.generation.answers import answer_sha256
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": False, "answer": "same text"}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "relevancy_score": 0.9, "answer_sha256": answer_sha256("same text")}]
    out = reconcile_scored_golden(golden_rows, stored)
    assert out[0]["faithfulness_score"] == 0.8


def test_reconcile_scored_golden_accepts_a_legacy_item_with_no_hash_field():
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": False, "answer": "any text at all"}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "relevancy_score": 0.9}]  # no answer_sha256: written before fix round 2
    out = reconcile_scored_golden(golden_rows, stored)
    assert out[0]["faithfulness_score"] == 0.8


# --- Fix round 3 finding A: the hash tripwire also fires on a failed row ------------

def test_reconcile_scored_golden_raises_when_a_failed_row_has_a_mismatched_stored_hash():
    # The real crash state: a rerun completed and scores.json was written with the new, completed
    # answer's hash, but the process crashed before answers.jsonl was replaced, so the row here is still
    # the stale failed run. The mismatch must be caught even though the row is currently failed.
    from evals.groundtruth.generation.answers import answer_sha256
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": True, "answer": "rate limit error"}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "relevancy_score": 0.9, "answer_sha256": answer_sha256("a completed, different answer")}]
    with pytest.raises(ValueError):
        reconcile_scored_golden(golden_rows, stored)


def test_reconcile_scored_golden_accepts_a_legacy_item_with_no_hash_field_on_a_failed_row():
    # A legacy score item (no answer_sha256) on a failed row keeps its fix round 1 behavior unchanged:
    # no hash check, verdict ignored, run_failed rendered.
    golden_rows = [{"id": "g-01", "category": "conceito", "run_failed": True, "answer": "rate limit error"}]
    stored = [{"id": "g-01", "category": "conceito", "no_retrieval": False, "faithfulness_score": 0.8,
              "relevancy_score": 0.9}]  # no answer_sha256
    out = reconcile_scored_golden(golden_rows, stored)
    assert out[0]["run_failed"] is True
    assert out[0]["faithfulness_score"] is None
