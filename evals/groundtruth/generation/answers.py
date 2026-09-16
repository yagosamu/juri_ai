"""Turns an agno RunOutput into one answers.jsonl row (Task 9b, brief R4).

Pure and agno-free: it only reads attributes (content, tools, metrics) that agno's RunOutput and
ToolExecution carry, so it works the same on the real object and on a fake built for tests.
"""
import hashlib

SEARCH_TOOL = "search_knowledge_base"
DATAJUD_TOOL = "search_datajud_api"
ERROR_STATUS = "ERROR"


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
