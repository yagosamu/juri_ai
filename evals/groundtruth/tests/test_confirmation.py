import json

import pytest

from evals.groundtruth.golden import confirm, finalize
from evals.groundtruth.golden.competitors import article_refs
from evals.groundtruth.golden.confirm import (calibrate, calibration_complete, calibration_problems,
                                              choose_calibration_sample, confirm_items, load_labels)
from evals.groundtruth.golden.finalize import FinalizeRefused, agreement_table, assemble, gate, render_report

CORPUS = {"cpc": "Art. 1º O prazo para contestar é de quinze dias úteis. "
                 "Art. 2º A coisa julgada torna imutável a decisão. "
                 "Art. 3º A petição inicial indicará o juízo."}


def _cand(cid, header, question="Pergunta?", category="conceito"):
    r = next(r for r in article_refs(CORPUS) if r.header == header)
    return {"candidate_id": cid, "doc_id": "cpc", "start": r.start, "end": r.end, "header": header,
            "question": question, "category": category}


def _row(cid, flagged, status="judged"):
    judge = None if status != "judged" else {"reasoning": "ok", "answerable": "yes", "also_answered_by": [],
                                             "leakage": "none", "category": "conceito"}
    return {"candidate_id": cid, "status": status, "flagged": flagged, "flag_reasons": ["x"] if flagged else [],
            "judge": judge, "judge_model": "gpt-4.1", "judged_at": "2026-09-14", "competitors": [],
            "signals": {"content_overlap": 0.1, "max_shared_ngram": 1, "cites_source": False}}


def _label(cid, decision, mode="calibrate", question="Pergunta?"):
    return {"candidate_id": cid, "mode": mode, "decision": decision, "reviewer": "yago",
            "reviewed_at": "2026-09-14", "question": question, "category": "conceito",
            "rubric": {"answerable": "yes", "also_answered_by": [], "leakage": "none"}}


def scripted(*answers):
    it = iter(answers)
    return lambda prompt: next(it)


def test_calibration_sample_is_deterministic_and_skips_refused():
    triage = {f"c{i:02d}": _row(f"c{i:02d}", False) for i in range(30)}
    triage["c00"]["status"] = "refused"
    first = choose_calibration_sample(triage, n=20, seed=7)
    assert first == choose_calibration_sample(triage, n=20, seed=7)
    assert len(first) == 20 and "c00" not in first


def test_calibrate_is_blind_and_records_the_rubric(tmp_path, capsys):
    row = _row("c1", False)
    row["judge"]["reasoning"] = "JUDGE_SECRET"
    labels = tmp_path / "labels.jsonl"
    calibrate([_cand("c1", "Art. 2º")], {"c1": row}, ["c1"], CORPUS, labels, "yago",
              scripted("y", "", "n", "conceito", "a"))
    assert "JUDGE_SECRET" not in capsys.readouterr().out
    saved = load_labels(labels)["c1"]
    assert saved["mode"] == "calibrate" and saved["decision"] == "accept" and saved["category"] == "conceito"
    assert saved["rubric"] == {"answerable": "yes", "also_answered_by": [], "leakage": "none"}


def test_calibrate_reprompts_on_an_unknown_competitor_label(tmp_path):
    row = _row("c1", False)
    row["competitors"] = [{"label": "C1", "ref_id": "cpc:0", "doc_id": "cpc", "header": "Art. 1º",
                           "start": 0, "end": 20, "methods": ["bm25"]}]
    labels = tmp_path / "labels.jsonl"
    calibrate([_cand("c1", "Art. 2º")], {"c1": row}, ["c1"], CORPUS, labels, "yago",
              scripted("p", "C7", "C1", "s", "procedimento", "r"))
    saved = load_labels(labels)["c1"]
    assert saved["rubric"]["also_answered_by"] == ["C1"] and saved["decision"] == "reject"


def test_calibrate_quit_saves_nothing(tmp_path):
    labels = tmp_path / "labels.jsonl"
    calibrate([_cand("c1", "Art. 2º")], {"c1": _row("c1", False)}, ["c1"], CORPUS, labels, "yago", scripted("q"))
    assert load_labels(labels) == {}


def test_calibration_complete_ignores_refused():
    triage = {"a": _row("a", False), "b": _row("b", False, status="refused")}
    assert calibration_complete(["a", "b"], triage, {"a": _label("a", "accept")})
    assert not calibration_complete(["a"], triage, {})


def test_confirm_flagged_shows_the_judge_and_saves_an_edit(tmp_path, capsys):
    row = _row("c2", True)
    row["judge"]["reasoning"] = "VISIBLE_REASONING"
    labels = tmp_path / "labels.jsonl"
    confirm_items([_cand("c2", "Art. 1º", question="Prazo?")], {"c2": row}, [], CORPUS, labels, "yago", "flagged",
                  scripted("e", "Qual o prazo para contestar?", "a"))
    assert "VISIBLE_REASONING" in capsys.readouterr().out
    saved = load_labels(labels)["c2"]
    assert saved["mode"] == "flagged" and saved["decision"] == "accept"
    assert saved["question"] == "Qual o prazo para contestar?"


def test_confirm_flagged_presents_only_flagged_unsampled_unlabeled(tmp_path):
    cands = [_cand("a", "Art. 1º"), _cand("b", "Art. 2º"), _cand("c", "Art. 3º")]
    triage = {"a": _row("a", True), "b": _row("b", False), "c": _row("c", True)}
    labels = tmp_path / "labels.jsonl"
    confirm_items(cands, triage, ["c"], CORPUS, labels, "yago", "flagged", scripted("r"))
    assert set(load_labels(labels)) == {"a"}


def _write_labels_with_truncated_tail(path):
    path.write_text(json.dumps(_label("c0", "accept"), ensure_ascii=False) + "\n"
                    + '{"candidate_id": "c1", "mode": "calib', encoding="utf-8")


def test_load_labels_ignores_a_truncated_last_line(tmp_path, capsys):
    labels = tmp_path / "labels.jsonl"
    _write_labels_with_truncated_tail(labels)
    assert list(load_labels(labels)) == ["c0"]
    assert "WARNING" in capsys.readouterr().err


def test_calibrate_appends_cleanly_after_a_truncated_last_line(tmp_path):
    labels = tmp_path / "labels.jsonl"
    _write_labels_with_truncated_tail(labels)
    cands = [_cand("c0", "Art. 1º"), _cand("c1", "Art. 2º")]
    triage = {"c0": _row("c0", False), "c1": _row("c1", False)}
    calibrate(cands, triage, ["c0", "c1"], CORPUS, labels, "yago", scripted("y", "", "n", "conceito", "a"))
    text = labels.read_text(encoding="utf-8")
    assert text.endswith("\n") and text.count("\n") == 2
    rows = [json.loads(line) for line in text.splitlines()]
    assert [(r["candidate_id"], r["decision"]) for r in rows] == [("c0", "accept"), ("c1", "accept")]


def test_load_labels_raises_on_a_malformed_interior_line(tmp_path):
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps(_label("c0", "accept")) + "\nnot json\n" + json.dumps(_label("c1", "reject")) + "\n",
                      encoding="utf-8")
    with pytest.raises(ValueError):
        load_labels(labels)


def test_gate_fails_on_a_single_false_accept():
    triage = {"a": _row("a", False), "b": _row("b", True)}
    result = gate(["a", "b"], triage, {"a": _label("a", "reject"), "b": _label("b", "accept")})
    assert result["false_accepts"] == ["a"] and result["false_rejects"] == ["b"] and result["passed"] is False


def test_gate_refuses_an_incomplete_sample():
    with pytest.raises(FinalizeRefused):
        gate(["a"], {"a": _row("a", False)}, {})


def test_assemble_assigns_modes_and_refuses_missing_decisions():
    cands = {c["candidate_id"]: c for c in [_cand("s", "Art. 1º"), _cand("f", "Art. 2º"), _cand("u", "Art. 3º")]}
    triage = {"s": _row("s", False), "f": _row("f", True), "u": _row("u", False)}
    labels = {"s": _label("s", "accept"), "f": _label("f", "accept", mode="flagged", question="Editada?")}
    by_id = {i.id: i for i in assemble(cands, triage, labels, ["s"], gate_passed=True)}
    assert by_id["s"].review_mode == "human_blind_calibration"
    assert by_id["f"].review_mode == "human_flagged" and by_id["f"].question == "Editada?"
    assert by_id["u"].review_mode == "judge_pass" and by_id["u"].reviewed_by == "judge:gpt-4.1"
    with pytest.raises(FinalizeRefused):
        assemble(cands, triage, labels, ["s"], gate_passed=False)
    with pytest.raises(FinalizeRefused):
        assemble(cands, triage, {"s": labels["s"]}, ["s"], gate_passed=True)


def test_assemble_excludes_rejected_and_refused():
    cands = {c["candidate_id"]: c for c in [_cand("s", "Art. 1º"), _cand("x", "Art. 2º")]}
    triage = {"s": _row("s", False), "x": _row("x", False, status="refused")}
    assert assemble(cands, triage, {"s": _label("s", "reject")}, ["s"], gate_passed=True) == []


def test_render_report_states_the_gate_and_modes():
    cands = {c["candidate_id"]: c for c in [_cand("s", "Art. 1º"), _cand("u", "Art. 2º")]}
    triage = {"s": _row("s", False), "u": _row("u", False)}
    labels = {"s": _label("s", "accept")}
    result = {"n": 1, "false_accepts": [], "false_rejects": [], "passed": True}
    items = assemble(cands, triage, labels, ["s"], gate_passed=True)
    text = render_report(triage, ["s"], result, agreement_table(["s"], triage, labels), items, labels)
    assert "passed" in text
    assert "| judge_pass | 1 |" in text and "| human_blind_calibration | 1 |" in text


def test_calibration_complete_requires_a_calibrate_label():
    triage = {"a": _row("a", False)}
    assert not calibration_complete(["a"], triage, {"a": _label("a", "accept", mode="flagged")})


@pytest.mark.parametrize("decision", ["accept", "reject"])
@pytest.mark.parametrize("sampled, flagged, expected, found", [
    (True, False, "calibrate", "flagged"),
    (False, True, "flagged", "unflagged"),
    (False, False, "unflagged", "calibrate"),
])
def test_assemble_refuses_a_label_from_the_wrong_review_path(sampled, flagged, expected, found, decision):
    cands = {"x1": _cand("x1", "Art. 1º")}
    triage = {"x1": _row("x1", flagged)}
    labels = {"x1": _label("x1", decision, mode=found)}
    with pytest.raises(FinalizeRefused) as exc:
        assemble(cands, triage, labels, ["x1"] if sampled else [], gate_passed=True)
    assert f"x1: expected label mode {expected!r}" in str(exc.value) and f"found {found!r}" in str(exc.value)


def _isolate_finalize(tmp_path, monkeypatch, triage):
    monkeypatch.setattr(finalize, "load_triage", lambda path: triage)
    monkeypatch.setattr(finalize, "CALIBRATION_SAMPLE", tmp_path / "calibration_sample.json")
    monkeypatch.setattr(finalize, "HUMAN_LABELS", tmp_path / "labels.jsonl")
    monkeypatch.setattr(finalize, "GOLDEN_SET", tmp_path / "golden_set.jsonl")
    monkeypatch.setattr(finalize, "CALIBRATION_REPORT", tmp_path / "golden_calibration.md")
    monkeypatch.setattr(finalize, "load_candidates", lambda: [])


def test_finalize_main_exits_cleanly_without_triage_rows(tmp_path, monkeypatch):
    _isolate_finalize(tmp_path, monkeypatch, {})
    with pytest.raises(SystemExit, match="no triage rows"):
        finalize.main()
    assert not (tmp_path / "golden_set.jsonl").exists()


def test_finalize_main_exits_cleanly_without_a_calibration_sample(tmp_path, monkeypatch):
    _isolate_finalize(tmp_path, monkeypatch, {"a": _row("a", False)})
    with pytest.raises(SystemExit, match="confirm --mode calibrate"):
        finalize.main()
    assert not (tmp_path / "golden_set.jsonl").exists()


def test_calibration_problems_names_missing_and_wrong_mode_labels():
    ids = ["cand-ok", "cand-wrong", "cand-missing", "cand-refused"]
    triage = {cid: _row(cid, False) for cid in ids}
    triage["cand-refused"]["status"] = "refused"
    labels = {"cand-ok": _label("cand-ok", "accept"), "cand-wrong": _label("cand-wrong", "reject", mode="flagged")}
    problems = calibration_problems(ids, triage, labels)
    assert len(problems) == 2
    assert problems[0].startswith("cand-wrong:") and "'flagged'" in problems[0]
    assert problems[1].startswith("cand-missing:") and "flagged" not in problems[1]
    assert calibration_problems(["cand-ok", "cand-refused"], triage, labels) == []


def test_calibrate_reports_a_wrong_mode_label_without_presenting_or_counting_it(tmp_path, capsys):
    labels = tmp_path / "human_labels.jsonl"
    labels.write_text(json.dumps(_label("cand-wrong", "accept", mode="flagged")) + "\n", encoding="utf-8")
    cands = [_cand("cand-wrong", "Art. 1º"), _cand("cand-new", "Art. 2º")]
    triage = {"cand-wrong": _row("cand-wrong", False), "cand-new": _row("cand-new", False)}
    calibrate(cands, triage, ["cand-wrong", "cand-new"], CORPUS, labels, "yago",
              scripted("y", "", "n", "conceito", "a"))
    out = capsys.readouterr().out
    assert "calibration: 0 of 2 done" in out
    warning = next(line for line in out.splitlines() if "cand-wrong" in line)
    assert "'flagged'" in warning and "human_labels.jsonl" in warning
    assert "[cand-wrong] CPC" not in out
    saved = load_labels(labels)
    assert saved["cand-wrong"]["mode"] == "flagged" and saved["cand-new"]["mode"] == "calibrate"


def test_confirm_main_exit_names_calibration_problems_and_caps_them(tmp_path, monkeypatch):
    ids = [f"s{i:02d}" for i in range(12)]
    sample = tmp_path / "calibration_sample.json"
    sample.write_text(json.dumps({"seed": 1, "n": 12, "candidate_ids": ids}), encoding="utf-8")
    labels = tmp_path / "human_labels.jsonl"
    labels.write_text(json.dumps(_label("s00", "accept", mode="flagged")) + "\n", encoding="utf-8")
    monkeypatch.setattr(confirm, "load_triage", lambda path: {cid: _row(cid, False) for cid in ids})
    monkeypatch.setattr(confirm, "CALIBRATION_SAMPLE", sample)
    monkeypatch.setattr(confirm, "HUMAN_LABELS", labels)
    monkeypatch.setattr(confirm, "load_corpus", lambda: CORPUS)
    monkeypatch.setattr(confirm, "load_candidates", lambda: [])
    with pytest.raises(SystemExit) as exc:
        confirm.main("flagged", "yago")
    message = str(exc.value)
    assert "--mode calibrate" in message and "human_labels.jsonl" in message
    assert "s00: " in message and "'flagged'" in message and "s09: " in message
    assert "s10: " not in message and "s11: " not in message and "2 more" in message
