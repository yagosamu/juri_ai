"""R5: faithfulness and answer relevancy on the 30 golden answers, scored with DeepEval.

deepeval is imported only inside score_golden_answers, and only when the caller has not injected
fake metric/test-case classes, so importing this module (and collecting its tests) never needs
DeepEval installed. CI never installs requirements-local.txt, so this keeps test collection green.
"""
import os
from collections import Counter, defaultdict

from evals.groundtruth.generation.answers import answer_sha256, assert_stored_hashes_present, is_failed_run

# The 2026-09-30 run died after the answers were already paid for: DeepEval's faithfulness metric
# raised openai.ContentFilterFinishReasonError from _a_generate_truths on one case, and the exception
# took the whole run with it. A judge call the content filter refuses is recorded per metric instead,
# excluded from that metric's mean and counted in the report, so one refused call costs one metric on
# one row. It is not retried: the judges run at temperature 0 and the filter is deterministic for the
# same input, so a retry would be refused again. It is also not "run_failed", which means the agent
# errored, nor "no_retrieval", which means the agent did not search; here the agent did both fine.
CONTENT_FILTER_REASON = "content_filter"


def _content_filter_errors() -> tuple:
    """The exception classes that mean "the content filter refused this judge call".

    Resolved lazily, and narrowly: only openai's own content-filter error. Everything else, a bad key,
    a network fault, a DeepEval bug, still propagates, because recording those as unscored rows would
    quietly shrink every mean instead of failing. Returns () when openai is not installed, which is the
    CI case where no real judge runs anyway.
    """
    try:
        from openai import ContentFilterFinishReasonError
    except ImportError:
        return ()
    return (ContentFilterFinishReasonError,)


def _measure_or_content_filter(metric, test_case, content_filter_errors: tuple) -> bool:
    """Runs metric.measure(test_case). True when it scored, False when the content filter refused it."""
    try:
        metric.measure(test_case)
    except content_filter_errors:
        return False
    return True


def _failed_result(row: dict, prior_attempts: list | None = None) -> dict:
    return {"id": row["id"], "category": row["category"], "run_failed": True, "no_retrieval": False,
           "relevancy_score": None, "relevancy_reason": None, "relevancy_cost": None,
           "relevancy_error": None, "faithfulness_score": None, "faithfulness_reason": None,
           "faithfulness_cost": None, "faithfulness_error": None,
           "answer_sha256": answer_sha256(row.get("answer", "")), "prior_attempts": prior_attempts or []}


def score_golden_answers(rows: list[dict], model: str = "gpt-4.1-mini", threshold: float = 0.5,
                         faithfulness_cls=None, relevancy_cls=None, test_case_cls=None,
                         content_filter_errors: tuple | None = None) -> list[dict]:
    """Faithfulness (only when the row searched and has contexts) and relevancy (always) per row.

    An answer with searched False, or with empty contexts, gets no faithfulness score: faithfulness
    against no context is undefined. Its relevancy is still scored. [""] is never passed as a
    stand-in context; a row with no context passes retrieval_context=None instead.

    A failed run (fix round 1: agno returned an API error as the "answer") gets neither score and is
    marked run_failed; no DeepEval call is made for it, since an error string is not an answer to judge.

    A judge call the content filter refuses leaves that one metric unscored, with
    <metric>_error = CONTENT_FILTER_REASON and no score and no cost, and the other metric on the same
    row is still scored. See CONTENT_FILTER_REASON for why it is neither retried nor folded into
    run_failed or no_retrieval. content_filter_errors overrides the exception classes caught, for tests.
    """
    if faithfulness_cls is None or relevancy_cls is None or test_case_cls is None:
        os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
        from deepeval.test_case import LLMTestCase
        faithfulness_cls = faithfulness_cls or FaithfulnessMetric
        relevancy_cls = relevancy_cls or AnswerRelevancyMetric
        test_case_cls = test_case_cls or LLMTestCase
    if content_filter_errors is None:
        content_filter_errors = _content_filter_errors()

    results = []
    for row in rows:
        if is_failed_run(row):
            results.append(_failed_result(row))
            continue

        has_context = bool(row.get("searched")) and bool(row.get("contexts"))
        retrieval_context = list(row["contexts"]) if has_context else None

        relevancy_case = test_case_cls(input=row["question"], actual_output=row["answer"],
                                       retrieval_context=retrieval_context)
        relevancy_metric = relevancy_cls(threshold=threshold, model=model, include_reason=True)
        relevancy_scored = _measure_or_content_filter(relevancy_metric, relevancy_case, content_filter_errors)

        result = {
            "id": row["id"], "category": row["category"], "run_failed": False, "no_retrieval": not has_context,
            "relevancy_score": relevancy_metric.score if relevancy_scored else None,
            "relevancy_reason": relevancy_metric.reason if relevancy_scored else None,
            "relevancy_cost": getattr(relevancy_metric, "evaluation_cost", None) if relevancy_scored else None,
            "relevancy_error": None if relevancy_scored else CONTENT_FILTER_REASON,
            "faithfulness_score": None, "faithfulness_reason": None, "faithfulness_cost": None,
            "faithfulness_error": None,
            "answer_sha256": answer_sha256(row["answer"]), "prior_attempts": [],
        }
        if has_context:
            faithfulness_case = test_case_cls(input=row["question"], actual_output=row["answer"],
                                              retrieval_context=retrieval_context)
            faithfulness_metric = faithfulness_cls(threshold=threshold, model=model, include_reason=True)
            if _measure_or_content_filter(faithfulness_metric, faithfulness_case, content_filter_errors):
                result.update(faithfulness_score=faithfulness_metric.score,
                              faithfulness_reason=faithfulness_metric.reason,
                              faithfulness_cost=getattr(faithfulness_metric, "evaluation_cost", None))
            else:
                result.update(faithfulness_error=CONTENT_FILTER_REASON)
        results.append(result)
    return results


def reconcile_scored_golden(golden_rows: list[dict], stored_scored: list[dict],
                            require_hash: bool = False) -> list[dict]:
    """Rebuilds golden score rows from an already-written scores.json ("golden" list) without calling
    DeepEval again: a row whose answer is a failed run is replaced with a run_failed result (its stored
    verdict, if any, is ignored); every other row's stored score is kept as-is, just tagged run_failed:
    False. Used by --report-only. Raises if a non-failed golden row has no stored score to reuse.

    Tripwire (fix round 2 ruling 2b, extended by fix round 3 finding A): when the stored score item
    carries answer_sha256, it must equal the hash of the current row's answer text, or this raises naming
    the id, since that score was computed for a different answer and would otherwise be silently reused.
    This check runs whether or not the current row is a failed run: a crash between the scores.json and
    answers.jsonl writes in score_and_write_only leaves scores.json holding the rerun's new score (hashed
    against its completed answer) next to a stale, still-failed answers.jsonl row, and that mismatch must
    be caught here rather than silently rendered. A stored item with no answer_sha256 is a legacy item
    (written before fix round 2) and is accepted as-is, on either a completed or a failed row.

    require_hash (Task 20) removes that legacy tolerance: a stored item with no answer_sha256 raises
    naming the ids, instead of being reused against answers it may never have been computed from.
    --report-only passes True, because it publishes a committed report. Default False, so every other
    caller behaves exactly as before.
    """
    if require_hash:
        assert_stored_hashes_present(golden_rows, stored_scored, "Stored DeepEval scores")
    stored_by_id = {s["id"]: s for s in stored_scored}
    out = []
    for row in golden_rows:
        stored = stored_by_id.get(row["id"])
        if stored is not None:
            stored_hash = stored.get("answer_sha256")
            if stored_hash is not None and stored_hash != answer_sha256(row["answer"]):
                raise ValueError(f"{row['id']}: stored DeepEval score's answer_sha256 does not match the current "
                                 f"answer text; rerun --only {row['id']} to regenerate a consistent answer "
                                 "and score")
        if is_failed_run(row):
            # DeepEval is never called on a failed golden run (score_golden_answers skips it), so unlike
            # abstention there is no per-row spend of its own to preserve here; only prior_attempts from
            # an earlier, since-replaced attempt (if any) needs carrying through.
            out.append(_failed_result(row, prior_attempts=(stored or {}).get("prior_attempts", [])))
            continue
        if stored is None:
            raise ValueError(f"{row['id']}: no stored DeepEval score in scores.json, and it is not a failed run")
        out.append({**stored, "run_failed": False})
    return out


def _mean_n(values: list) -> dict:
    return {"mean": (sum(values) / len(values)) if values else None, "n": len(values)}


def aggregate_faithfulness_relevancy(results: list[dict]) -> dict:
    """Means per category and overall, with n for each mean, the no-retrieval count, the run_failed
    count, and the count of metrics left unscored by a judge.

    A run_failed row (fix round 1) is excluded from both the faithfulness and the relevancy mean, and
    counted separately: an error string was never scored, in either direction. A no-retrieval row (a
    completed run that just did not search) is excluded from the faithfulness mean only and counted
    separately; its relevancy score still contributes to the relevancy mean.

    A metric with no score on a row that is neither run_failed nor no-retrieval is one a judge left
    unscored, the content-filter case above. It is excluded from that metric's mean only, and counted
    in unscored_faithfulness / unscored_relevancy with its reason in unscored_reasons, so a mean over
    fewer cases is always reported alongside the number of cases missing from it. The no-retrieval
    count and the unscored counts are kept apart: they are different reasons and must not be conflated.
    """
    by_category = defaultdict(lambda: {"faithfulness": [], "relevancy": []})
    overall = {"faithfulness": [], "relevancy": []}
    no_retrieval = 0
    run_failed = 0
    unscored = {"faithfulness": 0, "relevancy": 0}
    reasons = Counter()

    def take(metric: str, r: dict) -> None:
        score = r.get(f"{metric}_score")
        if score is None:
            unscored[metric] += 1
            reasons[r.get(f"{metric}_error") or CONTENT_FILTER_REASON] += 1
            return
        by_category[r["category"]][metric].append(score)
        overall[metric].append(score)

    for r in results:
        if r.get("run_failed"):
            run_failed += 1
            continue
        # Touch the category so it still appears in the table, with n=0, when every metric on every
        # row of that category was left unscored.
        by_category[r["category"]]
        if r["no_retrieval"]:
            no_retrieval += 1
        else:
            take("faithfulness", r)
        take("relevancy", r)

    return {
        "by_category": {cat: {"faithfulness": _mean_n(v["faithfulness"]), "relevancy": _mean_n(v["relevancy"])}
                        for cat, v in sorted(by_category.items())},
        "overall": {"faithfulness": _mean_n(overall["faithfulness"]), "relevancy": _mean_n(overall["relevancy"])},
        "no_retrieval": no_retrieval,
        "run_failed": run_failed,
        "unscored_faithfulness": unscored["faithfulness"],
        "unscored_relevancy": unscored["relevancy"],
        "unscored_reasons": dict(reasons),
    }
