import json
from types import SimpleNamespace

import pytest

from evals.groundtruth.generation.abstention import (RUN_FAILED_LABEL, AbstentionVerdict, abstention_counts,
                                                      abstention_label, anthropic_abstention_check,
                                                      openai_abstention_check, relabel_stored_abstention,
                                                      run_abstention)
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL
from evals.groundtruth.golden.triage import JUDGE_MODEL, MAX_JUDGE_ATTEMPTS, JudgeError

VALID_YES = {"reasoning": "A resposta diz que não há base nos documentos e não responde ao mérito.",
            "abstained": "yes"}
VALID_NO = {"reasoning": "A resposta traz um número e uma conclusão jurídica direta.", "abstained": "no"}


class TransportError(Exception):
    """Stands in for an openai.APIError or anthropic transport error: must propagate."""


def _openai_response(content, usage=(10, 5)):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]))


class FakeOpenAI:
    """Each reply is a message-content string to wrap in a fake response, or an exception to raise."""

    def __init__(self, replies, usage=(10, 5)):
        self.replies, self.calls, self.kwargs = list(replies), 0, []
        self.usage = usage
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return _openai_response(reply, self.usage)


def _anthropic_response(stop_reason, parsed, usage=(7, 3)):
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed,
                           usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]))


class FakeAnthropic:
    """Each reply is a fake response (built by _anthropic_response) or an exception to raise."""

    def __init__(self, replies):
        self.replies, self.calls, self.kwargs = list(replies), 0, []
        self.messages = self

    def parse(self, **kwargs):
        self.calls += 1
        self.kwargs.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


# --- OpenAI path ---------------------------------------------------------------

def test_openai_abstention_check_returns_verdict_and_usage():
    client = FakeOpenAI([json.dumps(VALID_YES)], usage=(20, 6))
    verdict, usage = openai_abstention_check(client, "Pergunta?", "Não encontrei base nos documentos.")
    assert verdict.abstained == "yes"
    assert usage == {"input_tokens": 20, "output_tokens": 6}


def test_openai_abstention_check_sends_temperature_zero_and_json_response_format():
    client = FakeOpenAI([json.dumps(VALID_NO)])
    openai_abstention_check(client, "Pergunta?", "Resposta.")
    sent = client.kwargs[0]
    assert sent["temperature"] == 0
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["model"] == JUDGE_MODEL


def test_openai_abstention_check_retries_on_bad_output_then_recovers():
    client = FakeOpenAI(["not json", json.dumps(VALID_YES)])
    verdict, _ = openai_abstention_check(client, "Pergunta?", "Resposta.")
    assert verdict.abstained == "yes"
    assert client.calls == 2


def test_openai_abstention_check_raises_judge_error_after_max_attempts():
    client = FakeOpenAI(["not json"] * MAX_JUDGE_ATTEMPTS)
    with pytest.raises(JudgeError):
        openai_abstention_check(client, "Pergunta?", "Resposta.")
    assert client.calls == MAX_JUDGE_ATTEMPTS


def test_openai_abstention_check_lets_a_transport_error_propagate():
    client = FakeOpenAI([TransportError("connection reset")])
    with pytest.raises(TransportError):
        openai_abstention_check(client, "Pergunta?", "Resposta.")


def test_openai_abstention_check_rejects_an_unknown_extra_key():
    bad = json.dumps({**VALID_YES, "extra_field": 1})
    client = FakeOpenAI([bad, bad])
    with pytest.raises(JudgeError):
        openai_abstention_check(client, "Pergunta?", "Resposta.")


# --- Anthropic path --------------------------------------------------------------

def test_anthropic_abstention_check_returns_verdict_and_usage():
    verdict = AbstentionVerdict.model_validate(VALID_NO)
    client = FakeAnthropic([_anthropic_response("end_turn", verdict, usage=(9, 2))])
    result, usage = anthropic_abstention_check(client, "Pergunta?", "Resposta.")
    assert result.abstained == "no"
    assert usage == {"input_tokens": 9, "output_tokens": 2}


def test_anthropic_abstention_check_sends_temperature_zero_via_extra_body():
    verdict = AbstentionVerdict.model_validate(VALID_YES)
    client = FakeAnthropic([_anthropic_response("end_turn", verdict)])
    anthropic_abstention_check(client, "Pergunta?", "Resposta.")
    sent = client.kwargs[0]
    assert "temperature" not in sent
    assert sent["extra_body"] == {"temperature": 0}
    assert sent["model"] == ANTHROPIC_JUDGE_MODEL
    assert sent["output_format"] is AbstentionVerdict


def test_anthropic_abstention_check_retries_on_non_end_turn_stop_reason():
    verdict = AbstentionVerdict.model_validate(VALID_YES)
    client = FakeAnthropic([_anthropic_response("refusal", None), _anthropic_response("end_turn", verdict)])
    result, _ = anthropic_abstention_check(client, "Pergunta?", "Resposta.")
    assert result.abstained == "yes"
    assert client.calls == 2


def test_anthropic_abstention_check_lets_a_transport_error_propagate():
    client = FakeAnthropic([TransportError("boom")])
    with pytest.raises(TransportError):
        anthropic_abstention_check(client, "Pergunta?", "Resposta.")


# --- Aggregation -----------------------------------------------------------------

def _judges(oa, an):
    return {JUDGE_MODEL: oa, ANTHROPIC_JUDGE_MODEL: an}


def test_abstention_label_yes_yes_is_abstained():
    judges = _judges({"verdict": {"abstained": "yes"}, "error": None},
                     {"verdict": {"abstained": "yes"}, "error": None})
    assert abstention_label(judges) == "abstained"


def test_abstention_label_no_no_is_answered():
    judges = _judges({"verdict": {"abstained": "no"}, "error": None},
                     {"verdict": {"abstained": "no"}, "error": None})
    assert abstention_label(judges) == "answered"


def test_abstention_label_yes_no_is_disagreement():
    judges = _judges({"verdict": {"abstained": "yes"}, "error": None},
                     {"verdict": {"abstained": "no"}, "error": None})
    assert abstention_label(judges) == "disagreement"


def test_abstention_label_a_judge_error_is_unverified():
    judges = _judges({"verdict": None, "error": "boom"}, {"verdict": {"abstained": "yes"}, "error": None})
    assert abstention_label(judges) == "unverified"


def test_abstention_counts_totals_the_four_labels():
    results = [{"label": "abstained"}, {"label": "abstained"}, {"label": "answered"},
              {"label": "disagreement"}, {"label": "unverified"}]
    counts = abstention_counts(results)
    assert counts == {"abstained": 2, "answered": 1, "disagreement": 1, "unverified": 1, "run_failed": 0}


def test_run_abstention_end_to_end_with_fake_clients():
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID_YES)]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response(
                  "end_turn", AbstentionVerdict.model_validate(VALID_YES))])}
    rows = [{"id": "oos-01", "question": "Pergunta fora de escopo?", "answer": "Não encontrei base.",
            "run_failed": False}]
    results = run_abstention(rows, clients)
    assert results[0]["label"] == "abstained"
    assert results[0]["judges"][JUDGE_MODEL]["usage"]["input_tokens"] == 10


def test_run_abstention_records_an_error_for_a_failed_judge():
    clients = {JUDGE_MODEL: FakeOpenAI(["not json", "not json"]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response(
                  "end_turn", AbstentionVerdict.model_validate(VALID_YES))])}
    rows = [{"id": "oos-02", "question": "Pergunta?", "answer": "Resposta.", "run_failed": False}]
    results = run_abstention(rows, clients)
    assert results[0]["label"] == "unverified"
    assert results[0]["judges"][JUDGE_MODEL]["error"] is not None


# --- Fix round 1: failed runs ---------------------------------------------------------

def test_run_abstention_labels_a_failed_run_and_calls_no_judge():
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID_YES)]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response(
                  "end_turn", AbstentionVerdict.model_validate(VALID_YES))])}
    rows = [{"id": "oos-01", "question": "Pergunta?", "answer": "Request too large ... TPM Limit 30000",
            "run_failed": True}]
    results = run_abstention(rows, clients)
    assert results[0]["label"] == "run_failed"
    assert results[0]["judges"] == {}
    assert clients[JUDGE_MODEL].calls == 0


def test_run_failed_judge_usage_is_counted_in_cost_while_its_verdict_is_ignored_for_labels():
    """Fix round 2 ruling 3's mandated test."""
    results = [{"id": "oos-01", "label": RUN_FAILED_LABEL,
               "judges": {JUDGE_MODEL: {"verdict": {"abstained": "no"}, "error": None,
                         "usage": {"input_tokens": 267, "output_tokens": 62}}}}]
    counts = abstention_counts(results)
    assert counts["run_failed"] == 1
    assert counts["answered"] == 0  # the "no" verdict never counts toward a label
    from evals.groundtruth.generation.run_generation import abstention_judge_usage
    assert abstention_judge_usage(results, JUDGE_MODEL) == {"input_tokens": 267, "output_tokens": 62}


def test_abstention_counts_reports_run_failed_separately():
    results = [{"label": "answered"}, {"label": "run_failed"}, {"label": "run_failed"}]
    counts = abstention_counts(results)
    assert counts["run_failed"] == 2
    assert counts["answered"] == 1


def test_relabel_stored_abstention_relabels_a_failed_row_ignoring_the_verdict_but_keeping_the_usage():
    # Fix round 2, owner resolution: the judge calls on a failed run's error text were real, paid calls,
    # so their usage is kept for cost purposes even though the verdict itself is discarded for the label.
    oos_rows = [{"id": "oos-01", "question": "Pergunta?", "run_failed": True}]
    stored = [{"id": "oos-01", "question": "Pergunta?",
              "judges": {JUDGE_MODEL: {"verdict": {"abstained": "no"}, "error": None,
                        "usage": {"input_tokens": 267, "output_tokens": 62}},
                        ANTHROPIC_JUDGE_MODEL: {"verdict": {"abstained": "no"}, "error": None,
                        "usage": {"input_tokens": 545, "output_tokens": 120}}},
              "label": "answered"}]
    out = relabel_stored_abstention(oos_rows, stored)
    assert out[0]["label"] == "run_failed"
    assert out[0]["judges"][JUDGE_MODEL]["usage"] == {"input_tokens": 267, "output_tokens": 62}
    assert out[0]["judges"][ANTHROPIC_JUDGE_MODEL]["usage"] == {"input_tokens": 545, "output_tokens": 120}


def test_relabel_stored_abstention_a_failed_row_with_nothing_stored_has_no_usage():
    oos_rows = [{"id": "oos-99", "question": "Pergunta?", "run_failed": True}]
    out = relabel_stored_abstention(oos_rows, stored_results=[])
    assert out[0]["label"] == "run_failed"
    assert out[0]["judges"] == {}


def test_relabel_stored_abstention_keeps_a_completed_rows_stored_verdicts():
    oos_rows = [{"id": "oos-02", "question": "Pergunta?", "run_failed": False}]
    stored_judges = {JUDGE_MODEL: {"verdict": {"abstained": "yes"}, "error": None, "usage": {"input_tokens": 1,
                     "output_tokens": 1}}, ANTHROPIC_JUDGE_MODEL: {"verdict": {"abstained": "yes"}, "error": None,
                     "usage": {"input_tokens": 1, "output_tokens": 1}}}
    stored = [{"id": "oos-02", "question": "Pergunta?", "judges": stored_judges, "label": "abstained"}]
    out = relabel_stored_abstention(oos_rows, stored)
    assert out[0]["label"] == "abstained"
    assert out[0]["judges"] == stored_judges


def test_relabel_stored_abstention_raises_when_a_non_failed_row_has_no_stored_verdict():
    oos_rows = [{"id": "oos-99", "question": "Pergunta?", "run_failed": False}]
    with pytest.raises(ValueError):
        relabel_stored_abstention(oos_rows, stored_results=[])


# --- Fix round 2: answer_sha256 tripwire --------------------------------------------

def _judges_pair(abstained_a="no", abstained_b="no"):
    return {JUDGE_MODEL: {"verdict": {"abstained": abstained_a}, "error": None,
                          "usage": {"input_tokens": 5, "output_tokens": 2}},
           ANTHROPIC_JUDGE_MODEL: {"verdict": {"abstained": abstained_b}, "error": None,
                                   "usage": {"input_tokens": 5, "output_tokens": 2}}}


def test_run_abstention_writes_answer_sha256_on_a_completed_row():
    from evals.groundtruth.generation.answers import answer_sha256
    clients = {JUDGE_MODEL: FakeOpenAI([json.dumps(VALID_YES)]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response(
                  "end_turn", AbstentionVerdict.model_validate(VALID_YES))])}
    rows = [{"id": "oos-01", "question": "q", "answer": "Não encontrei base.", "run_failed": False}]
    results = run_abstention(rows, clients)
    assert results[0]["answer_sha256"] == answer_sha256("Não encontrei base.")


def test_run_abstention_writes_answer_sha256_on_a_failed_row():
    from evals.groundtruth.generation.answers import answer_sha256
    clients = {JUDGE_MODEL: FakeOpenAI([]), ANTHROPIC_JUDGE_MODEL: FakeAnthropic([])}
    rows = [{"id": "oos-01", "question": "q", "answer": "rate limit error text", "run_failed": True}]
    results = run_abstention(rows, clients)
    assert results[0]["answer_sha256"] == answer_sha256("rate limit error text")


def test_relabel_stored_abstention_raises_when_the_stored_hash_does_not_match_the_current_answer():
    from evals.groundtruth.generation.answers import answer_sha256
    oos_rows = [{"id": "oos-02", "question": "q", "run_failed": False, "answer": "new answer"}]
    stored = [{"id": "oos-02", "question": "q", "judges": _judges_pair(),
              "answer_sha256": answer_sha256("a different, older answer")}]
    with pytest.raises(ValueError):
        relabel_stored_abstention(oos_rows, stored)


def test_relabel_stored_abstention_accepts_a_matching_hash():
    from evals.groundtruth.generation.answers import answer_sha256
    oos_rows = [{"id": "oos-02", "question": "q", "run_failed": False, "answer": "same answer"}]
    stored = [{"id": "oos-02", "question": "q", "judges": _judges_pair(),
              "answer_sha256": answer_sha256("same answer")}]
    out = relabel_stored_abstention(oos_rows, stored)
    assert out[0]["label"] == "answered"


def test_relabel_stored_abstention_accepts_a_legacy_item_with_no_hash_field():
    oos_rows = [{"id": "oos-02", "question": "q", "run_failed": False, "answer": "any text"}]
    stored = [{"id": "oos-02", "question": "q", "judges": _judges_pair()}]  # no answer_sha256: legacy
    out = relabel_stored_abstention(oos_rows, stored)
    assert out[0]["label"] == "answered"


# --- Fix round 3 finding A: the hash tripwire also fires on a failed row ------------

def test_relabel_stored_abstention_raises_when_a_failed_row_has_a_mismatched_stored_hash():
    # The real crash state: a rerun completed and scores.json was written with the new, completed
    # answer's hash, but the process crashed before answers.jsonl was replaced, so the row here is still
    # the stale failed run. The mismatch must be caught even though the row is currently failed.
    from evals.groundtruth.generation.answers import answer_sha256
    oos_rows = [{"id": "oos-01", "question": "q", "run_failed": True, "answer": "rate limit error text"}]
    stored = [{"id": "oos-01", "question": "q", "judges": _judges_pair(),
              "answer_sha256": answer_sha256("a completed, different answer")}]
    with pytest.raises(ValueError):
        relabel_stored_abstention(oos_rows, stored)


def test_relabel_stored_abstention_accepts_a_legacy_item_with_no_hash_field_on_a_failed_row():
    oos_rows = [{"id": "oos-01", "question": "q", "run_failed": True, "answer": "rate limit error text"}]
    stored = [{"id": "oos-01", "question": "q", "judges": _judges_pair(), "label": "answered"}]  # no hash
    out = relabel_stored_abstention(oos_rows, stored)
    assert out[0]["label"] == "run_failed"
    assert out[0]["judges"] == _judges_pair()
