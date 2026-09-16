import hashlib
from types import SimpleNamespace

from evals.groundtruth.generation.answers import answer_sha256, build_answer_row, is_failed_run


def _tool(name, result):
    return SimpleNamespace(tool_name=name, result=result)


def test_build_answer_row_extracts_contexts_tool_calls_and_flags_in_order():
    run = SimpleNamespace(
        content="A resposta é X.",
        tools=[_tool("search_knowledge_base", "trecho 1"), _tool("search_datajud_api", "{}"),
               _tool("search_knowledge_base", "trecho 2")],
        metrics=SimpleNamespace(input_tokens=120, output_tokens=45),
    )
    item = {"id": "g-01", "question": "Pergunta?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["id"] == "g-01"
    assert row["question"] == "Pergunta?"
    assert row["category"] == "conceito"
    assert row["answer"] == "A resposta é X."
    assert row["contexts"] == ["trecho 1", "trecho 2"]
    assert row["tool_calls"] == ["search_knowledge_base", "search_datajud_api", "search_knowledge_base"]
    assert row["searched"] is True
    assert row["datajud_called"] is True
    assert row["usage"] == {"input_tokens": 120, "output_tokens": 45}


def test_build_answer_row_no_tools_means_not_searched_and_no_datajud():
    run = SimpleNamespace(content="Não sei.", tools=[], metrics=SimpleNamespace(input_tokens=10, output_tokens=5))
    item = {"id": "oos-01", "question": "Pergunta fora de escopo?", "category": "fora_de_escopo"}
    row = build_answer_row(item, run)
    assert row["contexts"] == []
    assert row["tool_calls"] == []
    assert row["searched"] is False
    assert row["datajud_called"] is False


def test_build_answer_row_handles_none_tools():
    run = SimpleNamespace(content="x", tools=None, metrics=SimpleNamespace(input_tokens=1, output_tokens=1))
    item = {"id": "g-02", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["tool_calls"] == []
    assert row["searched"] is False


def test_build_answer_row_stringifies_non_str_content():
    run = SimpleNamespace(content={"foo": "bar"}, tools=[], metrics=SimpleNamespace(input_tokens=1, output_tokens=1))
    item = {"id": "g-03", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["answer"] == str({"foo": "bar"})


def test_build_answer_row_handles_missing_metrics():
    run = SimpleNamespace(content="x", tools=[], metrics=None)
    item = {"id": "g-04", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["usage"] == {"input_tokens": 0, "output_tokens": 0}


def test_build_answer_row_only_datajud_called_means_searched_false():
    run = SimpleNamespace(content="x", tools=[_tool("search_datajud_api", "{}")],
                          metrics=SimpleNamespace(input_tokens=1, output_tokens=1))
    item = {"id": "g-05", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["searched"] is False
    assert row["datajud_called"] is True
    assert row["contexts"] == []


# --- Fix round 1: status / run_failed / error --------------------------------------

class FakeRunStatus:
    """Stands in for agno's RunStatus, a str Enum: str(status) gives "RunStatus.error", not the plain
    value "ERROR", so build_answer_row must read .value, not str()."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"RunStatus.{self.value.lower()}"


def test_build_answer_row_records_completed_status_and_run_failed_false():
    run = SimpleNamespace(content="Resposta ok.", tools=[], status=FakeRunStatus("COMPLETED"),
                          metrics=SimpleNamespace(input_tokens=100, output_tokens=20))
    item = {"id": "g-06", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["status"] == "COMPLETED"
    assert row["run_failed"] is False
    assert "error" not in row


def test_build_answer_row_records_error_status_run_failed_and_error_text():
    error_text = ("Request too large for gpt-4o in organization org-x on tokens per min (TPM): "
                 "Limit 30000, Requested 40571.")
    run = SimpleNamespace(content=error_text, tools=[], status=FakeRunStatus("ERROR"),
                          metrics=SimpleNamespace(input_tokens=0, output_tokens=0))
    item = {"id": "oos-01", "question": "Pergunta?", "category": "fora_de_escopo"}
    row = build_answer_row(item, run)
    assert row["status"] == "ERROR"
    assert row["run_failed"] is True
    assert row["error"] == error_text
    assert row["answer"] == error_text


def test_build_answer_row_handles_a_run_with_no_status_attribute_at_all():
    run = SimpleNamespace(content="x", tools=[], metrics=SimpleNamespace(input_tokens=1, output_tokens=1))
    item = {"id": "g-07", "question": "?", "category": "conceito"}
    row = build_answer_row(item, run)
    assert row["status"] is None
    assert row["run_failed"] is False


def test_is_failed_run_uses_the_run_failed_field_when_present():
    assert is_failed_run({"run_failed": True, "usage": {"input_tokens": 500}, "tool_calls": ["x"]}) is True
    assert is_failed_run({"run_failed": False, "usage": {"input_tokens": 0}, "tool_calls": []}) is False


def test_is_failed_run_legacy_fallback_zero_input_tokens_and_no_tool_calls():
    legacy_failed = {"usage": {"input_tokens": 0, "output_tokens": 0}, "tool_calls": []}
    assert is_failed_run(legacy_failed) is True


def test_is_failed_run_legacy_fallback_a_real_completed_run_is_not_failed():
    legacy_ok = {"usage": {"input_tokens": 15305, "output_tokens": 110}, "tool_calls": ["search_knowledge_base"]}
    assert is_failed_run(legacy_ok) is False


def test_is_failed_run_legacy_fallback_zero_tokens_but_a_tool_call_is_not_failed():
    # a real (if unusual) run that happened to use zero billed tokens but still called a tool
    legacy_edge = {"usage": {"input_tokens": 0, "output_tokens": 0}, "tool_calls": ["search_knowledge_base"]}
    assert is_failed_run(legacy_edge) is False


# --- Fix round 2: answer_sha256 -----------------------------------------------------

def test_answer_sha256_matches_hashlib_directly():
    assert answer_sha256("A resposta é X.") == hashlib.sha256("A resposta é X.".encode("utf-8")).hexdigest()


def test_answer_sha256_is_deterministic():
    assert answer_sha256("mesmo texto") == answer_sha256("mesmo texto")


def test_answer_sha256_differs_for_different_text():
    assert answer_sha256("texto a") != answer_sha256("texto b")


def test_answer_sha256_handles_empty_string():
    assert answer_sha256("") == hashlib.sha256(b"").hexdigest()
