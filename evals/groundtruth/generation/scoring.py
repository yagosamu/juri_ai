"""R5: faithfulness and answer relevancy on the 30 golden answers, scored with DeepEval.

deepeval is imported only inside score_golden_answers, and only when the caller has not injected
fake metric/test-case classes, so importing this module (and collecting its tests) never needs
DeepEval installed. CI never installs requirements-local.txt, so this keeps test collection green.
"""
import os
from collections import defaultdict

from evals.groundtruth.generation.answers import answer_sha256, is_failed_run


def _failed_result(row: dict, prior_attempts: list | None = None) -> dict:
    return {"id": row["id"], "category": row["category"], "run_failed": True, "no_retrieval": False,
           "relevancy_score": None, "relevancy_reason": None, "relevancy_cost": None,
           "faithfulness_score": None, "faithfulness_reason": None, "faithfulness_cost": None,
           "answer_sha256": answer_sha256(row.get("answer", "")), "prior_attempts": prior_attempts or []}


def score_golden_answers(rows: list[dict], model: str = "gpt-4.1-mini", threshold: float = 0.5,
                         faithfulness_cls=None, relevancy_cls=None, test_case_cls=None) -> list[dict]:
    """Faithfulness (only when the row searched and has contexts) and relevancy (always) per row.

    An answer with searched False, or with empty contexts, gets no faithfulness score: faithfulness
    against no context is undefined. Its relevancy is still scored. [""] is never passed as a
    stand-in context; a row with no context passes retrieval_context=None instead.

    A failed run (fix round 1: agno returned an API error as the "answer") gets neither score and is
    marked run_failed; no DeepEval call is made for it, since an error string is not an answer to judge.
    """
    if faithfulness_cls is None or relevancy_cls is None or test_case_cls is None:
        os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
        from deepeval.test_case import LLMTestCase
        faithfulness_cls = faithfulness_cls or FaithfulnessMetric
        relevancy_cls = relevancy_cls or AnswerRelevancyMetric
        test_case_cls = test_case_cls or LLMTestCase

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
        relevancy_metric.measure(relevancy_case)

        result = {
            "id": row["id"], "category": row["category"], "run_failed": False, "no_retrieval": not has_context,
            "relevancy_score": relevancy_metric.score, "relevancy_reason": relevancy_metric.reason,
            "relevancy_cost": getattr(relevancy_metric, "evaluation_cost", None),
            "faithfulness_score": None, "faithfulness_reason": None, "faithfulness_cost": None,
            "answer_sha256": answer_sha256(row["answer"]), "prior_attempts": [],
        }
        if has_context:
            faithfulness_case = test_case_cls(input=row["question"], actual_output=row["answer"],
                                              retrieval_context=retrieval_context)
            faithfulness_metric = faithfulness_cls(threshold=threshold, model=model, include_reason=True)
            faithfulness_metric.measure(faithfulness_case)
            result.update(faithfulness_score=faithfulness_metric.score,
                          faithfulness_reason=faithfulness_metric.reason,
                          faithfulness_cost=getattr(faithfulness_metric, "evaluation_cost", None))
        results.append(result)
    return results


def reconcile_scored_golden(golden_rows: list[dict], stored_scored: list[dict]) -> list[dict]:
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
    """
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
    """Means per category and overall, with n for each mean, the no-retrieval count, and the
    run_failed count.

    A run_failed row (fix round 1) is excluded from both the faithfulness and the relevancy mean, and
    counted separately: an error string was never scored, in either direction. A no-retrieval row (a
    completed run that just did not search) is excluded from the faithfulness mean only and counted
    separately; its relevancy score still contributes to the relevancy mean.
    """
    by_category = defaultdict(lambda: {"faithfulness": [], "relevancy": []})
    overall = {"faithfulness": [], "relevancy": []}
    no_retrieval = 0
    run_failed = 0
    for r in results:
        if r.get("run_failed"):
            run_failed += 1
            continue
        if r["no_retrieval"]:
            no_retrieval += 1
        else:
            by_category[r["category"]]["faithfulness"].append(r["faithfulness_score"])
            overall["faithfulness"].append(r["faithfulness_score"])
        by_category[r["category"]]["relevancy"].append(r["relevancy_score"])
        overall["relevancy"].append(r["relevancy_score"])

    return {
        "by_category": {cat: {"faithfulness": _mean_n(v["faithfulness"]), "relevancy": _mean_n(v["relevancy"])}
                        for cat, v in sorted(by_category.items())},
        "overall": {"faithfulness": _mean_n(overall["faithfulness"]), "relevancy": _mean_n(overall["relevancy"])},
        "no_retrieval": no_retrieval,
        "run_failed": run_failed,
    }
