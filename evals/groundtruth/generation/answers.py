"""Turns an agno RunOutput into one answers.jsonl row (Task 9b, brief R4).

Pure and agno-free: it only reads attributes (content, tools, metrics) that agno's RunOutput and
ToolExecution carry, so it works the same on the real object and on a fake built for tests.
"""
import hashlib
import statistics

SEARCH_TOOL = "search_knowledge_base"
DATAJUD_TOOL = "search_datajud_api"
ERROR_STATUS = "ERROR"

# The Tier 1 OpenAI gpt-4o tokens-per-minute limit the 3 pre-adoption out-of-scope runs exceeded
# (results/generation_pre_adoption.md, "Failed runs"): a single turn asked for 39229 to 40571 tokens.
TPM_LIMIT = 30000


def answer_sha256(answer: str) -> str:
    """sha256 of the exact answer text (fix round 2 ruling 2b), used as a tripwire: a score or verdict
    item records the hash of the answer it was computed from, and a reader can detect a stale item by
    comparing it to the hash of whatever answer currently sits in answers.jsonl for that id."""
    return hashlib.sha256((answer or "").encode("utf-8")).hexdigest()


def _status_value(status) -> str | None:
    """A plain string for agno's RunStatus (a str Enum: str(status) gives "RunStatus.error", not the
    value "ERROR" the brief asks for), or the value unchanged when it is already a plain string (as in
    a test fake) or None when the run carries no status at all."""
    if status is None:
        return None
    return getattr(status, "value", status)


def build_answer_row(item: dict, run) -> dict:
    tools = run.tools or []
    tool_calls = [t.tool_name for t in tools]
    contexts = [str(t.result) for t in tools if t.tool_name == SEARCH_TOOL]
    metrics = run.metrics
    usage = {
        "input_tokens": getattr(metrics, "input_tokens", 0) if metrics is not None else 0,
        "output_tokens": getattr(metrics, "output_tokens", 0) if metrics is not None else 0,
    }
    status = _status_value(getattr(run, "status", None))
    run_failed = status == ERROR_STATUS
    row = {
        "id": item["id"],
        "question": item["question"],
        "category": item["category"],
        "answer": str(run.content),
        "contexts": contexts,
        "tool_calls": tool_calls,
        "searched": SEARCH_TOOL in tool_calls,
        "datajud_called": DATAJUD_TOOL in tool_calls,
        "usage": usage,
        "status": status,
        "run_failed": run_failed,
    }
    if run_failed:
        # agno sets run_response.content = str(e) on error (agent.py:1261-1306), so the error text is
        # already in "answer"; recorded again under its own key per the brief so callers never have to
        # infer "this is an error" by re-parsing the answer field.
        row["error"] = str(run.content)
    return row


def is_failed_run(row: dict) -> bool:
    """True when row is a failed agent run, never a real answer.

    Uses row["run_failed"] when the row has it (every row build_answer_row writes from here on). For a
    legacy row written before this field existed, falls back to: zero input tokens and no tool calls at
    all, since a completed gpt-4o run always consumes at least some input tokens.
    """
    if "run_failed" in row:
        return bool(row["run_failed"])
    usage = row.get("usage") or {}
    return usage.get("input_tokens", 0) == 0 and not row.get("tool_calls")


def assert_stored_hashes_present(rows: list[dict], stored_items: list[dict], kind: str) -> None:
    """Raise unless every stored score item that matches a row carries an answer_sha256.

    The per-item tripwire in reconcile_scored_golden and relabel_stored_abstention can only fire when
    the stored item has a hash to compare, so an item written before that field existed is reused
    unchecked. That is safe for a file that was written alongside its own answers, and dangerous the
    moment answers.jsonl has been rewritten since: on 2026-09-30 the whole pre-adoption scores.json
    was hashless, and --report-only would have rendered its 5000/0 verdicts as the 1500/150 result
    without an error. Callers that re-render a committed report pass require_hash=True to refuse that.

    A row with no stored item at all is not this error; the caller raises its own for that.
    """
    stored_by_id = {s["id"]: s for s in stored_items}
    missing = [row["id"] for row in rows
               if row["id"] in stored_by_id and stored_by_id[row["id"]].get("answer_sha256") is None]
    if not missing:
        return None
    raise ValueError(
        f"{kind} in generation/scores.json carry no answer_sha256 for {len(missing)} id(s), so they "
        f"cannot be matched to the answers now in generation/answers.jsonl and were computed before "
        f"them: {', '.join(missing)}. Score the answers on disk with --score-only, which calls the "
        f"judges and costs money; --report-only can only re-render verdicts that already match.")


def input_tokens_per_turn(rows: list[dict]) -> dict:
    """Task 20 ruling 3: how many input tokens one agent turn sent, over a set of answer rows.

    One row is one turn, read from row["usage"]["input_tokens"] as build_answer_row writes it; a row
    with no usage at all counts as a turn of 0 tokens rather than being dropped. Returns count, mean,
    median, max and over_tpm_limit, the number of rows strictly above TPM_LIMIT, plus that limit so a
    report never has to restate it.

    This only summarizes the rows it is given. A failed run records 0 input tokens of its own (agno
    returned the rate-limit error instead of a completed turn, and the tokens it asked for are in the
    error text, not in usage), so the caller decides whether to filter failed rows out with
    is_failed_run before summarizing. Nothing here changes how answers are written.
    """
    tokens = [(row.get("usage") or {}).get("input_tokens", 0) for row in rows]
    if not tokens:
        return {"count": 0, "mean": None, "median": None, "max": None,
                "over_tpm_limit": 0, "tpm_limit": TPM_LIMIT}
    return {
        "count": len(tokens),
        "mean": statistics.fmean(tokens),
        "median": statistics.median(tokens),
        "max": max(tokens),
        "over_tpm_limit": sum(1 for n in tokens if n > TPM_LIMIT),
        "tpm_limit": TPM_LIMIT,
    }
