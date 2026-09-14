import json

import pytest

from evals.groundtruth.golden.competitors import article_refs
from evals.groundtruth.golden.judges import (ANTHROPIC_JUDGE_MODEL, RUBRIC_V2, anthropic_judge, openai_judge_v2,
                                             run_judgments)
from evals.groundtruth.golden.triage import JUDGE_MODEL, JudgeError, JudgeVerdict, judge

CORPUS = {"cpc": "Art. 1º O prazo para contestar é de quinze dias úteis. "
                 "Art. 2º A coisa julgada torna imutável a decisão. "
                 "Art. 3º A petição inicial indicará o juízo."}
VALID = {"reasoning": "O artigo responde.", "answerable": "yes", "also_answered_by": [],
         "leakage": "none", "category": "conceito"}


def _ref(header):
    return next(r for r in article_refs(CORPUS) if r.header == header)


def _cand(cid, header, question="Pergunta?", category="conceito"):
    r = _ref(header)
    return {"candidate_id": cid, "doc_id": "cpc", "start": r.start, "end": r.end, "header": header,
            "question": question, "category": category}


def _competitor(header, label):
    r = _ref(header)
    return {"label": label, "ref_id": r.ref_id, "doc_id": "cpc", "header": header,
            "start": r.start, "end": r.end, "methods": ["bm25"]}


def _triage_row(cid, status="judged", competitors=None):
    return {"candidate_id": cid, "status": status, "competitors": competitors or [],
            "flagged": False, "flag_reasons": []}


class FakeOpenAI:
    def __init__(self, replies):
        self.replies, self.calls, self.prompts = list(replies), 0, []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        self.prompts.append(kwargs["messages"][0]["content"])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        message = type("Message", (), {"content": reply})
        return type("Response", (), {"choices": [type("Choice", (), {"message": message})]})


class FakeAnthropic:
    def __init__(self, replies):
        self.replies, self.calls, self.kwargs = list(replies), 0, []
        self.messages = self

    def parse(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        stop_reason, parsed = reply
        return type("Response", (), {"stop_reason": stop_reason, "parsed_output": parsed})


def _verdict(**change):
    return JudgeVerdict.model_validate({**VALID, **change})


def test_rubric_v2_carries_the_operational_definitions():
    for phrase in ("sozinho, contém a resposta completa", "Tratar de tema parecido não conta",
                   "condições de validade", "valor, prazo, número, parte ou fato único"):
        assert phrase in RUBRIC_V2
    for placeholder in ("{question}", "{header}", "{article}", "{competitors}"):
        assert placeholder in RUBRIC_V2


def test_triage_judge_still_defaults_to_the_v1_prompt():
    client = FakeOpenAI([json.dumps(VALID)])
    judge(client, "q?", "Art. 1º", "texto", [], CORPUS)
    assert "Tratar de tema parecido não conta" not in client.prompts[0]


def test_both_judges_receive_the_identical_v2_prompt():
    competitors = [_competitor("Art. 2º", "C1")]
    openai_client = FakeOpenAI([json.dumps(VALID)])
    anthropic_client = FakeAnthropic([("end_turn", _verdict())])
    openai_judge_v2(openai_client, "q?", "Art. 1º", "texto", competitors, CORPUS)
    anthropic_judge(anthropic_client, "q?", "Art. 1º", "texto", competitors, CORPUS)
    assert openai_client.prompts[0] == anthropic_client.kwargs[0]["messages"][0]["content"]
    assert "Tratar de tema parecido não conta" in openai_client.prompts[0]


def test_anthropic_judge_uses_haiku_at_temperature_zero_with_the_verdict_schema():
    client = FakeAnthropic([("end_turn", _verdict())])
    assert anthropic_judge(client, "q?", "Art. 1º", "texto", [], CORPUS).answerable == "yes"
    sent = client.kwargs[0]
    assert sent["model"] == ANTHROPIC_JUDGE_MODEL == "claude-haiku-4-5"
    assert "temperature" not in sent and sent["extra_body"] == {"temperature": 0}
    assert sent["output_format"] is JudgeVerdict


def test_anthropic_judge_retries_after_a_refusal():
    client = FakeAnthropic([("refusal", None), ("end_turn", _verdict())])
    assert anthropic_judge(client, "q?", "Art. 1º", "texto", [], CORPUS).category == "conceito"
    assert client.calls == 2


def test_anthropic_judge_fails_after_two_unusable_outputs():
    client = FakeAnthropic([("end_turn", None), ("max_tokens", None)])
    with pytest.raises(JudgeError):
        anthropic_judge(client, "q?", "Art. 1º", "texto", [], CORPUS)
    assert client.calls == 2


def test_anthropic_judge_rejects_unknown_competitor_labels():
    bad = _verdict(also_answered_by=["C9"])
    client = FakeAnthropic([("end_turn", bad), ("end_turn", bad)])
    with pytest.raises(JudgeError):
        anthropic_judge(client, "q?", "Art. 1º", "texto", [_competitor("Art. 2º", "C1")], CORPUS)


def test_anthropic_judge_treats_a_schema_validation_error_as_a_failed_attempt():
    client = FakeAnthropic([ValueError("output does not match the schema"), ("end_turn", _verdict())])
    assert anthropic_judge(client, "q?", "Art. 1º", "texto", [], CORPUS).answerable == "yes"
    assert client.calls == 2


def test_anthropic_transport_errors_propagate():
    client = FakeAnthropic([RuntimeError("network down")])
    with pytest.raises(RuntimeError):
        anthropic_judge(client, "q?", "Art. 1º", "texto", [], CORPUS)


def test_run_judgments_writes_both_judges_skips_refused_and_resumes(tmp_path):
    candidates = [_cand("a", "Art. 1º"), _cand("b", "Art. 2º")]
    triage = {"a": _triage_row("a"), "b": _triage_row("b", status="refused")}
    out = tmp_path / "judgments.jsonl"
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID)]), ANTHROPIC_JUDGE_MODEL: FakeAnthropic([("end_turn", _verdict())])}
    counts = run_judgments(candidates, triage, CORPUS, clients, out)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["candidate_id"] for r in rows] == ["a"] and counts["judged_rows"] == 1
    assert rows[0]["rubric_version"] == "v2"
    assert set(rows[0]["judges"]) == {JUDGE_MODEL, ANTHROPIC_JUDGE_MODEL}
    assert all(j["verdict"] and j["error"] is None for j in rows[0]["judges"].values())
    again = run_judgments(candidates, triage, CORPUS, {JUDGE_MODEL: FakeOpenAI([]), ANTHROPIC_JUDGE_MODEL: FakeAnthropic([])}, out)
    assert again["judged_rows"] == 0


def test_run_judgments_records_a_judge_failure_without_inventing_a_verdict(tmp_path):
    out = tmp_path / "judgments.jsonl"
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID)]),
               ANTHROPIC_JUDGE_MODEL: FakeAnthropic([("end_turn", None), ("end_turn", None)])}
    run_judgments([_cand("a", "Art. 1º")], {"a": _triage_row("a")}, CORPUS, clients, out)
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["judges"][ANTHROPIC_JUDGE_MODEL]["verdict"] is None
    assert row["judges"][ANTHROPIC_JUDGE_MODEL]["error"]
    assert row["judges"][JUDGE_MODEL]["verdict"]["answerable"] == "yes"


def test_run_judgments_requires_both_clients(tmp_path):
    with pytest.raises(ValueError):
        run_judgments([], {}, CORPUS, {JUDGE_MODEL: FakeOpenAI([])}, tmp_path / "j.jsonl")


def test_run_judgments_resumes_after_a_truncated_last_line(tmp_path):
    out = tmp_path / "judgments.jsonl"
    good = {"candidate_id": "a", "rubric_version": "v2", "judged_at": "2026-09-14",
            "judges": {JUDGE_MODEL: {"verdict": VALID, "error": None}, ANTHROPIC_JUDGE_MODEL: {"verdict": VALID, "error": None}}}
    out.write_text(json.dumps(good) + "\n" + '{"candidate_id": "b", "rub', encoding="utf-8")
    candidates = [_cand("a", "Art. 1º"), _cand("b", "Art. 2º")]
    triage = {"a": _triage_row("a"), "b": _triage_row("b")}
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID)]), ANTHROPIC_JUDGE_MODEL: FakeAnthropic([("end_turn", _verdict())])}
    run_judgments(candidates, triage, CORPUS, clients, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["candidate_id"] for line in lines] == ["a", "b"]
