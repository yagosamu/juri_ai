import json

import numpy as np
import pytest

from evals.groundtruth.golden.competitors import BM25, article_refs, find_competitors
from evals.groundtruth.golden.leakage import cites_source, content_tokens, fold, leakage_signals, max_shared_ngram
from evals.groundtruth.golden.triage import (JudgeError, JudgeVerdict, flag_reasons, judge, load_triage, rederive_file,
                                             rederive_flags, run_triage)

CORPUS = {
    "cpc": "Art. 1º O prazo para contestar é de quinze dias úteis contados da citação. "
           "Art. 2º A coisa julgada material torna imutável a decisão de mérito. "
           "Art. 3º A petição inicial indicará o juízo a que é dirigida.",
    "cdc": "Art. 1º O consumidor pode desistir do contrato no prazo de sete dias. "
           "Art. 2º O fornecedor responde pelos vícios do produto.",
}
VALID = {"reasoning": "O artigo responde a pergunta.", "answerable": "yes", "also_answered_by": [],
         "leakage": "none", "category": "conceito"}
CLEAN = {"content_overlap": 0.2, "max_shared_ngram": 2, "cites_source": False}


class TransportError(Exception):
    """Stands in for an openai.APIError: anything that is not a JudgeError must propagate."""


def _response(content):
    message = type("Message", (), {"content": content})
    choice = type("Choice", (), {"message": message})
    return type("Response", (), {"choices": [choice]})


class FakeClient:
    """Each reply is the message content to return, or an exception instance to raise from create()."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return _response(reply)


class RawResponseClient(FakeClient):
    """Each reply is a whole response object, for malformed response shapes."""

    def create(self, **kwargs):
        self.calls += 1
        return self.replies.pop(0)


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


def _ref(doc_id, header):
    return next(r for r in article_refs(CORPUS) if r.doc_id == doc_id and r.header == header)


def _competitor(doc_id, header, label):
    r = _ref(doc_id, header)
    return {"label": label, "ref_id": r.ref_id, "doc_id": r.doc_id, "header": r.header,
            "start": r.start, "end": r.end, "methods": ["bm25"]}


def _candidate(cid, doc_id, header, question, category="conceito"):
    r = _ref(doc_id, header)
    return {"candidate_id": cid, "doc_id": doc_id, "start": r.start, "end": r.end, "header": header,
            "question": question, "category": category}


def _triage_args(tmp_path):
    refs = article_refs(CORPUS)
    return FakeEmbedder(len(refs)), np.eye(len(refs), dtype=np.float32), refs, tmp_path / "triage.jsonl"


def test_fold_lowercases_and_strips_accents():
    assert fold("AÇÃO Úteis") == "acao uteis"


@pytest.mark.parametrize("question", [
    "O que não se torna coisa julgada segundo o artigo?",
    "Qual o prazo do art. 5º?",
    "O que diz a CLT sobre férias?",
    "Como a Lei Geral de Proteção de Dados trata o consentimento?",
    "O que diz a Lei 8.078/90 sobre o direito de arrependimento?",
    "Quem é o controlador segundo a Lei 13.709?",
    "O que prevê o § 1º sobre a prorrogação?",
    "O que o Decreto-Lei 5.452 regula?",
])
def test_cites_source_flags_references_to_a_source(question):
    assert cites_source(question)


@pytest.mark.parametrize("question", [
    "Qual o prazo para contestar uma ação?",
    "O que a lei diz sobre horas extras?",
])
def test_cites_source_passes_a_natural_question(question):
    assert not cites_source(question)


def test_max_shared_ngram_detects_copied_phrase_and_ignores_paraphrase():
    assert max_shared_ngram("Qual é o prazo para contestar é de quinze dias úteis?", CORPUS["cpc"]) >= 5
    assert max_shared_ngram("Em quanto tempo devo apresentar a defesa?", CORPUS["cpc"]) < 5


def test_leakage_signals_shape():
    signals = leakage_signals("Qual o prazo para contestar?", CORPUS["cpc"])
    assert set(signals) == {"content_overlap", "max_shared_ngram", "cites_source"}
    assert 0.0 <= signals["content_overlap"] <= 1.0


def test_bm25_ranks_document_with_rare_term_first():
    scores = BM25([["prazo", "contestar"], ["coisa", "julgada", "decisao"], ["prazo", "consumidor"]]).scores(["julgada"])
    assert scores.index(max(scores)) == 1
    assert scores[0] == 0.0 and scores[2] == 0.0


def test_article_refs_are_unique_and_start_at_their_headers():
    refs = article_refs(CORPUS)
    assert len(refs) == 5 and len({r.ref_id for r in refs}) == 5
    for r in refs:
        assert CORPUS[r.doc_id][r.start:r.end].startswith(r.header)


def test_find_competitors_excludes_golden_and_merges_methods():
    refs = article_refs(CORPUS)
    bm25 = BM25([content_tokens(CORPUS[r.doc_id][r.start:r.end]) for r in refs])
    golden = refs.index(_ref("cdc", "Art. 1º"))
    other = refs.index(_ref("cpc", "Art. 1º"))
    matrix = np.eye(len(refs), dtype=np.float32)
    found = find_competitors("Qual o prazo para desistir?", golden, refs, bm25, matrix[other].copy(), matrix)
    assert [c["ref_id"] for c in found] == [refs[other].ref_id]
    assert found[0]["methods"] == ["bm25", "dense"]


def test_verdict_rejects_extra_keys_blank_reasoning_and_bad_enum():
    JudgeVerdict.model_validate(VALID)
    for bad in ({**VALID, "start": 0}, {**VALID, "reasoning": "  "}, {**VALID, "answerable": "maybe"}):
        with pytest.raises(ValueError):
            JudgeVerdict.model_validate(bad)


def test_judge_returns_a_valid_verdict():
    client = FakeClient([json.dumps(VALID)])
    verdict = judge(client, "O que é coisa julgada?", "Art. 2º", "texto", [_competitor("cpc", "Art. 1º", "C1")], CORPUS)
    assert verdict.answerable == "yes" and client.calls == 1


def test_judge_retries_then_fails_on_an_unknown_competitor_label():
    bad = json.dumps({**VALID, "also_answered_by": ["C9"]})
    client = FakeClient([bad, bad])
    with pytest.raises(JudgeError):
        judge(client, "q?", "Art. 2º", "texto", [_competitor("cpc", "Art. 1º", "C1")], CORPUS)
    assert client.calls == 2


def test_judge_recovers_on_second_attempt():
    client = FakeClient(["not json", json.dumps(VALID)])
    assert judge(client, "q?", "Art. 2º", "texto", [], CORPUS).category == "conceito"
    assert client.calls == 2


def test_judge_treats_missing_content_as_an_invalid_attempt():
    client = FakeClient([None, None])
    with pytest.raises(JudgeError):
        judge(client, "q?", "Art. 2º", "texto", [], CORPUS)
    assert client.calls == 2


def test_judge_recovers_after_missing_content():
    client = FakeClient([None, json.dumps(VALID)])
    assert judge(client, "q?", "Art. 2º", "texto", [], CORPUS).answerable == "yes"
    assert client.calls == 2


@pytest.mark.parametrize("malformed", [
    type("Response", (), {"choices": []}),
    type("Response", (), {}),
    _response(123),
])
def test_judge_retries_a_malformed_response_shape(malformed):
    client = RawResponseClient([malformed, _response(json.dumps(VALID))])
    assert judge(client, "q?", "Art. 2º", "texto", [], CORPUS).category == "conceito"
    assert client.calls == 2


def test_clean_candidate_has_no_flags():
    assert flag_reasons("conceito", JudgeVerdict.model_validate(VALID), CLEAN, None) == []


@pytest.mark.parametrize("change, expected", [
    ({"answerable": "partial"}, "answerable=partial"),
    ({"also_answered_by": ["C1"]}, "also_answered_by=C1"),
    ({"leakage": "heavy"}, "leakage=heavy"),
    ({"category": "procedimento"}, "category_mismatch: stored=conceito judge=procedimento"),
])
def test_each_judge_rule_flags(change, expected):
    assert flag_reasons("conceito", JudgeVerdict.model_validate({**VALID, **change}), CLEAN, None) == [expected]


def test_leakage_some_does_not_flag():
    assert flag_reasons("conceito", JudgeVerdict.model_validate({**VALID, "leakage": "some"}), CLEAN, None) == []


def test_signal_rules_and_judge_failure_flag():
    signals = {**CLEAN, "cites_source": True, "max_shared_ngram": 5}
    assert flag_reasons("conceito", None, signals, "boom") == ["cites_source", "shared_ngram=5", "judge_failed: boom"]


def test_run_triage_writes_rows_resumes_and_refuses_bad_spans(tmp_path):
    refs = article_refs(CORPUS)
    matrix = np.eye(len(refs), dtype=np.float32)
    good = _candidate("r1-cpc-000", "cpc", "Art. 2º", "O que torna imutável uma decisão?")
    bad = {**_candidate("r1-cpc-001", "cpc", "Art. 3º", "Pergunta?"), "end": 10**9}
    out = tmp_path / "triage.jsonl"
    embedder = FakeEmbedder(len(refs))
    counts = run_triage([good, bad], CORPUS, FakeClient([json.dumps(VALID)]), embedder, matrix, refs, out)
    assert counts == {"judged": 1, "judge_failed": 0, "refused": 1, "skipped_existing": 0}
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["status"] for r in rows] == ["judged", "refused"]
    assert rows[0]["flagged"] is False and embedder.saved
    again = run_triage([good, bad], CORPUS, FakeClient([]), embedder, matrix, refs, out)
    assert again["skipped_existing"] == 2 and again["judged"] == 0


def test_run_triage_records_a_judge_failure_as_flagged(tmp_path):
    refs = article_refs(CORPUS)
    candidate = _candidate("r1-cdc-000", "cdc", "Art. 2º", "Quem responde pelos vícios?")
    out = tmp_path / "triage.jsonl"
    run_triage([candidate], CORPUS, FakeClient(["{}", "{}"]), FakeEmbedder(len(refs)),
               np.eye(len(refs), dtype=np.float32), refs, out)
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["status"] == "judge_failed" and row["flagged"] is True


def test_run_triage_lets_transport_errors_propagate_without_writing_a_row(tmp_path):
    embedder, matrix, refs, out = _triage_args(tmp_path)
    first = _candidate("r1-cpc-000", "cpc", "Art. 2º", "O que torna imutável uma decisão?")
    second = _candidate("r1-cdc-000", "cdc", "Art. 2º", "Quem responde pelos vícios?")
    with pytest.raises(TransportError):
        run_triage([first, second], CORPUS, FakeClient([json.dumps(VALID), TransportError("connection reset")]),
                   embedder, matrix, refs, out)
    assert list(load_triage(out)) == ["r1-cpc-000"]
    counts = run_triage([first, second], CORPUS, FakeClient([json.dumps(VALID)]), embedder, matrix, refs, out)
    assert counts == {"judged": 1, "judge_failed": 0, "refused": 0, "skipped_existing": 1}
    assert [r["status"] for r in load_triage(out).values()] == ["judged", "judged"]


def test_load_triage_ignores_a_truncated_last_line_and_run_triage_resumes(tmp_path, capsys):
    embedder, matrix, refs, out = _triage_args(tmp_path)
    first = _candidate("r1-cpc-000", "cpc", "Art. 2º", "O que torna imutável uma decisão?")
    second = _candidate("r1-cdc-000", "cdc", "Art. 2º", "Quem responde pelos vícios?")
    third = _candidate("r1-cpc-002", "cpc", "Art. 1º", "Em quanto tempo devo apresentar a defesa?")
    run_triage([first, second], CORPUS, FakeClient([json.dumps(VALID)] * 2), embedder, matrix, refs, out)
    with out.open("a", encoding="utf-8") as f:
        f.write('{"candidate_id": "r1-cpc-002", "judge_mo')
    capsys.readouterr()
    assert list(load_triage(out)) == ["r1-cpc-000", "r1-cdc-000"]
    warning = capsys.readouterr().err
    assert "WARNING" in warning and str(out) in warning
    counts = run_triage([first, second, third], CORPUS, FakeClient([json.dumps(VALID)]), embedder, matrix, refs, out)
    assert counts == {"judged": 1, "judge_failed": 0, "refused": 0, "skipped_existing": 2}
    assert str(out) in capsys.readouterr().err
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["candidate_id"] for r in rows] == ["r1-cpc-000", "r1-cdc-000", "r1-cpc-002"]


def test_load_triage_raises_on_a_malformed_middle_line(tmp_path):
    out = tmp_path / "triage.jsonl"
    out.write_text('{"candidate_id": "a"}\nnot json\n{"candidate_id": "b"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_triage(out)


def _judged_row(candidate, signals, flag_reasons_, flagged, judge_=VALID, judge_error=None, status="judged"):
    return {"candidate_id": candidate["candidate_id"], "judge_model": "gpt-4.1", "judged_at": "2026-09-14",
            "status": status, "signals": signals, "competitors": [_competitor("cpc", "Art. 1º", "C1")],
            "judge": judge_, "judge_error": judge_error, "flag_reasons": flag_reasons_, "flagged": flagged}


def test_rederive_flags_recomputes_signals_and_flags_but_keeps_every_other_field():
    citing = _candidate("r1-cdc-005", "cdc", "Art. 1º", "O que a Lei 8.078/90 diz sobre desistir do contrato?")
    failed = _candidate("r1-cdc-006", "cdc", "Art. 2º", "Quem responde pelos vícios?")
    refused_cand = {**_candidate("r1-cpc-007", "cpc", "Art. 3º", "Pergunta?"), "end": 10**9}
    citing_row = _judged_row(citing, {**CLEAN, "cites_source": False}, [], False)
    error = "judge failed after 2 attempts: boom"
    failed_row = _judged_row(failed, CLEAN, [f"judge_failed: {error}"], True, judge_=None, judge_error=error,
                             status="judge_failed")
    refused_row = {"candidate_id": "r1-cpc-007", "judge_model": "gpt-4.1", "judged_at": "2026-09-14",
                   "status": "refused", "refused_reason": "span invalid", "flagged": False, "flag_reasons": []}
    rows = [citing_row, failed_row, refused_row]
    snapshot = json.loads(json.dumps(rows))
    new = rederive_flags(rows, [citing, failed, refused_cand], CORPUS)
    assert rows == snapshot
    assert new[0]["signals"]["cites_source"] is True
    assert new[0]["flag_reasons"] == ["cites_source"] and new[0]["flagged"] is True
    assert new[1]["flag_reasons"] == [f"judge_failed: {error}"] and new[1]["flagged"] is True
    assert new[2] == refused_row
    derived = {"signals", "flag_reasons", "flagged"}
    for old_row, new_row in zip(rows[:2], new[:2]):
        assert list(new_row) == list(old_row)
        assert {k: v for k, v in new_row.items() if k not in derived} == {k: v for k, v in old_row.items()
                                                                           if k not in derived}


def test_rederive_file_rewrites_the_file_and_reports_changed_flags(tmp_path):
    citing = _candidate("r1-cdc-005", "cdc", "Art. 1º", "O que a Lei 8.078/90 diz sobre desistir do contrato?")
    out = tmp_path / "triage.jsonl"
    row = _judged_row(citing, {**CLEAN, "cites_source": False}, [], False)
    out.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    changes = rederive_file(out, [citing], CORPUS)
    assert changes == [("r1-cdc-005", [], ["cites_source"])]
    rewritten = load_triage(out)["r1-cdc-005"]
    assert rewritten["flagged"] is True and rewritten["judge"] == VALID
