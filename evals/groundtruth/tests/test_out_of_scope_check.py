import json
from types import SimpleNamespace

import numpy as np
import pytest

from evals.groundtruth.config import OUT_OF_SCOPE
from evals.groundtruth.golden.competitors import BM25, article_refs
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL, ANTHROPIC_MAX_TOKENS
from evals.groundtruth.golden.leakage import content_tokens
from evals.groundtruth.golden.triage import JUDGE_MODEL, MAX_JUDGE_ATTEMPTS, JudgeError
from evals.groundtruth.generation.out_of_scope_check import (ARTICLE_MAX_CHARS, CHECK_VERSION, OutOfScopeVerdict,
                                                              anthropic_check, article_block, candidate_articles,
                                                              load_out_of_scope, openai_check, render_report,
                                                              run_check, status_for)

CORPUS = {"cpc": "Art. 1º O prazo para contestar é de quinze dias úteis contados da citação. "
                 "Art. 2º A coisa julgada material torna imutável a decisão de mérito."}
VALID = {"reasoning": "Nenhum dos artigos contém a resposta, completa nem parcial.",
         "answered_by": [], "partially_answered_by": []}


class TransportError(Exception):
    """Stands in for an openai.APIError or anthropic transport error: must propagate."""


class FakeEmbedder:
    def __init__(self, dims):
        self.dims = dims
        self.saved = False

    def get_embedding(self, text):
        vector = [0.0] * self.dims
        vector[len(text) % self.dims] = 1.0
        return vector

    def save(self):
        self.saved = True


def _openai_response(content, usage=(10, 5)):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]))


class FakeOpenAI:
    """Each reply is a message-content string to wrap in a fake response, or an exception to raise."""

    def __init__(self, replies, usage=(10, 5)):
        self.replies, self.calls, self.prompts, self.kwargs = list(replies), 0, [], []
        self.usage = usage
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        self.prompts.append(kwargs["messages"][0]["content"])
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


def _refs():
    return article_refs(CORPUS)


def _bm25():
    refs = _refs()
    return BM25([content_tokens(CORPUS[r.doc_id][r.start:r.end]) for r in refs])


def _articles():
    refs = _refs()
    return [{"ref_id": refs[0].ref_id, "doc_id": refs[0].doc_id, "header": refs[0].header,
             "start": refs[0].start, "end": refs[0].end, "methods": ["bm25"], "label": "C1"},
            {"ref_id": refs[1].ref_id, "doc_id": refs[1].doc_id, "header": refs[1].header,
             "start": refs[1].start, "end": refs[1].end, "methods": ["dense"], "label": "C2"}]


def _row(idx, question, status, oa_verdict, an_verdict):
    return {"id": f"oos-{idx:02d}", "question": question, "check_version": CHECK_VERSION,
            "checked_at": "2026-09-15", "articles": [{"label": "C1"}],
            "judges": {JUDGE_MODEL: {"verdict": oa_verdict, "error": None if oa_verdict else "boom",
                                     "usage": {"input_tokens": 10, "output_tokens": 5} if oa_verdict else None},
                      ANTHROPIC_JUDGE_MODEL: {"verdict": an_verdict, "error": None if an_verdict else "boom",
                                              "usage": {"input_tokens": 8, "output_tokens": 3} if an_verdict else None}},
            "status": status}


# --- Loading -----------------------------------------------------------------

def test_load_out_of_scope_loads_the_ten_approved_questions():
    items = load_out_of_scope(OUT_OF_SCOPE)
    assert [item["id"] for item in items] == [f"oos-{n:02d}" for n in range(1, 11)]
    assert all(item["category"] == "fora_de_escopo" for item in items)
    assert items[0]["question"] == "Qual é a pena prevista para o crime de estelionato?"
    assert items[1]["question"] == ("Com quantos pontos na carteira de habilitação o motorista tem o direito "
                                    "de dirigir suspenso?")
    assert items[4]["question"] == "Qual é o prazo de validade do passaporte comum brasileiro?"
    assert items[6]["question"] == "Qual é o valor da multa para quem não vota nas eleições?"
    assert items[9]["question"] == "Quais documentos são necessários para registrar uma marca no INPI?"


def test_load_out_of_scope_raises_on_duplicate_id(tmp_path):
    path = tmp_path / "dup.jsonl"
    row = {"id": "oos-01", "question": "Pergunta?", "category": "fora_de_escopo", "expected_source": "x"}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_out_of_scope(path)


def test_load_out_of_scope_raises_on_wrong_category(tmp_path):
    path = tmp_path / "cat.jsonl"
    row = {"id": "oos-01", "question": "Pergunta?", "category": "fato_pontual", "expected_source": "x"}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_out_of_scope(path)


def test_load_out_of_scope_raises_on_blank_question(tmp_path):
    path = tmp_path / "blank.jsonl"
    row = {"id": "oos-01", "question": "   ", "category": "fora_de_escopo", "expected_source": "x"}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_out_of_scope(path)


def test_load_out_of_scope_raises_on_missing_key(tmp_path):
    path = tmp_path / "missing.jsonl"
    row = {"id": "oos-01", "question": "Pergunta?", "category": "fora_de_escopo"}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_out_of_scope(path)


# --- Articles and prompt ------------------------------------------------------

def test_candidate_articles_labels_in_order_and_never_excludes_an_article():
    refs, bm25 = _refs(), _bm25()
    matrix = np.eye(len(refs), dtype=np.float32)
    qvec = matrix[0].copy()  # matches ref 0 exactly, and shares no BM25 terms with either article
    articles = candidate_articles("xyzuvwqrst plexonimflorb", refs, bm25, qvec, matrix)
    assert articles[0]["ref_id"] == refs[0].ref_id  # would be excluded if it were the golden index
    assert [a["label"] for a in articles] == [f"C{n}" for n in range(1, len(articles) + 1)]
    for a in articles:
        assert set(a) == {"ref_id", "doc_id", "header", "start", "end", "methods", "label"}


def test_article_block_caps_article_text_and_marks_the_cut():
    long_corpus = {"cdc": "Art. 1º " + ("x" * 9000)}
    refs = article_refs(long_corpus)
    articles = [{"ref_id": refs[0].ref_id, "doc_id": "cdc", "header": refs[0].header, "start": refs[0].start,
                "end": refs[0].end, "methods": ["bm25"], "label": "C1"}]
    block = article_block(articles, long_corpus)
    assert block.startswith("[C1] CDC Art. 1º:")
    assert block.endswith(" [...]")
    text_part = block.split(": ", 1)[1][:-len(" [...]")]
    assert len(text_part) == ARTICLE_MAX_CHARS


def test_article_block_does_not_mark_a_short_article():
    refs = _refs()
    articles = [{"ref_id": refs[0].ref_id, "doc_id": refs[0].doc_id, "header": refs[0].header,
                "start": refs[0].start, "end": refs[0].end, "methods": ["bm25"], "label": "C1"}]
    block = article_block(articles, CORPUS)
    assert not block.endswith(" [...]")


def test_prompt_contains_the_question_and_every_label():
    articles = _articles()
    client = FakeOpenAI([json.dumps(VALID)])
    openai_check(client, "Minha pergunta de teste?", articles, CORPUS)
    sent = client.prompts[0]
    assert "Minha pergunta de teste?" in sent
    for a in articles:
        assert f"[{a['label']}]" in sent


# --- OpenAI path ---------------------------------------------------------------

def test_openai_check_returns_the_verdict_and_usage():
    client = FakeOpenAI([json.dumps(VALID)], usage=(12, 4))
    verdict, usage = openai_check(client, "Pergunta?", _articles(), CORPUS)
    assert verdict.answered_by == [] and verdict.partially_answered_by == []
    assert usage == {"input_tokens": 12, "output_tokens": 4}


def test_openai_check_sends_temperature_zero_and_json_response_format():
    client = FakeOpenAI([json.dumps(VALID)])
    openai_check(client, "Pergunta?", _articles(), CORPUS)
    sent = client.kwargs[0]
    assert sent["temperature"] == 0
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["model"] == JUDGE_MODEL


@pytest.mark.parametrize("bad_reply", [
    "not json",
    json.dumps({**VALID, "extra_field": 1}),
    json.dumps({**VALID, "answered_by": ["C9"]}),
    json.dumps({**VALID, "answered_by": ["C1"], "partially_answered_by": ["C1"]}),
])
def test_openai_check_counts_each_bad_output_as_a_failed_attempt(bad_reply):
    client = FakeOpenAI([bad_reply, bad_reply])
    with pytest.raises(JudgeError):
        openai_check(client, "Pergunta?", _articles(), CORPUS)
    assert client.calls == 2


def test_openai_check_recovers_on_the_second_attempt():
    client = FakeOpenAI(["not json", json.dumps(VALID)])
    verdict, _ = openai_check(client, "Pergunta?", _articles(), CORPUS)
    assert verdict.reasoning
    assert client.calls == 2


def test_openai_check_raises_judge_error_after_max_attempts():
    client = FakeOpenAI(["not json"] * MAX_JUDGE_ATTEMPTS)
    with pytest.raises(JudgeError):
        openai_check(client, "Pergunta?", _articles(), CORPUS)
    assert client.calls == MAX_JUDGE_ATTEMPTS


def test_openai_check_lets_a_transport_error_propagate():
    client = FakeOpenAI([TransportError("connection reset")])
    with pytest.raises(TransportError):
        openai_check(client, "Pergunta?", _articles(), CORPUS)


# --- Anthropic path --------------------------------------------------------------

def test_anthropic_check_retries_on_non_end_turn_stop_reason():
    verdict = OutOfScopeVerdict.model_validate(VALID)
    client = FakeAnthropic([_anthropic_response("refusal", None), _anthropic_response("end_turn", verdict)])
    result, _ = anthropic_check(client, "Pergunta?", _articles(), CORPUS)
    assert result.reasoning and client.calls == 2


def test_anthropic_check_retries_on_a_missing_parsed_output():
    verdict = OutOfScopeVerdict.model_validate(VALID)
    client = FakeAnthropic([_anthropic_response("end_turn", None), _anthropic_response("end_turn", verdict)])
    result, _ = anthropic_check(client, "Pergunta?", _articles(), CORPUS)
    assert result.reasoning and client.calls == 2


def test_anthropic_check_sends_temperature_zero_via_extra_body():
    verdict = OutOfScopeVerdict.model_validate(VALID)
    client = FakeAnthropic([_anthropic_response("end_turn", verdict)])
    anthropic_check(client, "Pergunta?", _articles(), CORPUS)
    sent = client.kwargs[0]
    assert "temperature" not in sent
    assert sent["extra_body"] == {"temperature": 0}
    assert sent["model"] == ANTHROPIC_JUDGE_MODEL
    assert sent["max_tokens"] == ANTHROPIC_MAX_TOKENS
    assert sent["output_format"] is OutOfScopeVerdict


def test_anthropic_check_reads_usage_from_input_and_output_tokens():
    verdict = OutOfScopeVerdict.model_validate(VALID)
    client = FakeAnthropic([_anthropic_response("end_turn", verdict, usage=(20, 6))])
    _, usage = anthropic_check(client, "Pergunta?", _articles(), CORPUS)
    assert usage == {"input_tokens": 20, "output_tokens": 6}


def test_anthropic_check_raises_judge_error_after_max_attempts():
    client = FakeAnthropic([_anthropic_response("end_turn", None), _anthropic_response("max_tokens", None)])
    with pytest.raises(JudgeError):
        anthropic_check(client, "Pergunta?", _articles(), CORPUS)
    assert client.calls == 2


def test_anthropic_check_lets_a_transport_error_propagate():
    client = FakeAnthropic([TransportError("network down")])
    with pytest.raises(TransportError):
        anthropic_check(client, "Pergunta?", _articles(), CORPUS)


# --- status_for -------------------------------------------------------------------

def test_status_for_out_of_scope_when_both_judges_find_nothing():
    judges = {"m1": {"verdict": {"answered_by": [], "partially_answered_by": []}, "error": None, "usage": {}},
             "m2": {"verdict": {"answered_by": [], "partially_answered_by": []}, "error": None, "usage": {}}}
    assert status_for(judges) == "out_of_scope"


def test_status_for_answerable_when_a_verdict_has_a_complete_label():
    judges = {"m1": {"verdict": {"answered_by": ["C1"], "partially_answered_by": []}, "error": None, "usage": {}},
             "m2": {"verdict": {"answered_by": [], "partially_answered_by": []}, "error": None, "usage": {}}}
    assert status_for(judges) == "answerable"


def test_status_for_answerable_on_a_partial_label_alone():
    judges = {"m1": {"verdict": {"answered_by": [], "partially_answered_by": ["C2"]}, "error": None, "usage": {}},
             "m2": {"verdict": {"answered_by": [], "partially_answered_by": []}, "error": None, "usage": {}}}
    assert status_for(judges) == "answerable"


def test_status_for_unverified_on_one_judge_error_even_when_the_other_found_nothing():
    judges = {"m1": {"verdict": None, "error": "boom", "usage": None},
             "m2": {"verdict": {"answered_by": [], "partially_answered_by": []}, "error": None, "usage": {}}}
    assert status_for(judges) == "unverified"


# --- run_check --------------------------------------------------------------------

def test_run_check_builds_rows_with_articles_judges_and_status():
    refs, bm25 = _refs(), _bm25()
    matrix = np.eye(len(refs), dtype=np.float32)
    embedder = FakeEmbedder(len(refs))
    items = [{"id": "oos-01", "question": "Primeira pergunta?", "category": "fora_de_escopo", "expected_source": "x"},
             {"id": "oos-02", "question": "Segunda pergunta?", "category": "fora_de_escopo", "expected_source": "y"}]
    reply = json.dumps(VALID)
    an_verdict = OutOfScopeVerdict.model_validate(VALID)
    clients = {JUDGE_MODEL: FakeOpenAI([reply, reply]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response("end_turn", an_verdict),
                                                    _anthropic_response("end_turn", an_verdict)])}
    rows = run_check(items, CORPUS, refs, bm25, embedder, matrix, clients)
    assert [r["id"] for r in rows] == ["oos-01", "oos-02"]
    for row, item in zip(rows, items):
        assert row["question"] == item["question"]
        assert row["check_version"] == CHECK_VERSION
        assert row["status"] == "out_of_scope"
        for a in row["articles"]:
            assert "text" not in a
        assert set(row["judges"]) == {JUDGE_MODEL, ANTHROPIC_JUDGE_MODEL}
        for info in row["judges"].values():
            assert info["verdict"] is not None and info["error"] is None and info["usage"]
    assert embedder.saved is False  # run_check itself does not save; main() does


def test_run_check_records_a_judge_error_from_one_client():
    refs, bm25 = _refs(), _bm25()
    matrix = np.eye(len(refs), dtype=np.float32)
    embedder = FakeEmbedder(len(refs))
    items = [{"id": "oos-01", "question": "Primeira pergunta?", "category": "fora_de_escopo", "expected_source": "x"}]
    an_verdict = OutOfScopeVerdict.model_validate(VALID)
    clients = {JUDGE_MODEL: FakeOpenAI(["not json", "not json"]),
              ANTHROPIC_JUDGE_MODEL: FakeAnthropic([_anthropic_response("end_turn", an_verdict)])}
    rows = run_check(items, CORPUS, refs, bm25, embedder, matrix, clients)
    row = rows[0]
    assert row["judges"][JUDGE_MODEL]["verdict"] is None and row["judges"][JUDGE_MODEL]["error"]
    assert row["judges"][ANTHROPIC_JUDGE_MODEL]["verdict"] is not None
    assert row["status"] == "unverified"


# --- render_report ------------------------------------------------------------------

def test_render_report_shows_counts_tokens_and_limitations_with_no_em_dash():
    oa_answerable = {"answered_by": ["C1"], "partially_answered_by": []}
    empty = {"answered_by": [], "partially_answered_by": []}
    rows = [_row(1, "Primeira pergunta?", "out_of_scope", empty, empty),
           _row(2, "Segunda pergunta?", "answerable", oa_answerable, empty)]
    report = render_report(rows)
    assert "out_of_scope: 1" in report
    assert "answerable: 1" in report
    assert "unverified: 0" in report
    assert str(20) in report  # 10 + 10 input tokens for gpt-4.1
    assert str(10) in report  # 5 + 5 output tokens for gpt-4.1
    assert str(16) in report  # 8 + 8 input tokens for claude-haiku-4-5
    assert str(6) in report  # 3 + 3 output tokens for claude-haiku-4-5
    assert "8000" in report
    assert "human legal review" in report.lower()
    assert "—" not in report
