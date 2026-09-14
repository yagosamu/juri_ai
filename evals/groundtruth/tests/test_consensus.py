import pytest

from evals.groundtruth.golden.consensus import (REVIEWER, ConsensusRefused, agreement_table, assemble, decide,
                                                majority_category, render_report)
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL, RUBRIC_VERSION
from evals.groundtruth.golden.schema import GoldenItem, LeakageSignals, Passage, load_golden, save_golden
from evals.groundtruth.golden.triage import JUDGE_MODEL

A, B = JUDGE_MODEL, ANTHROPIC_JUDGE_MODEL


def _cand(cid, category="conceito"):
    return {"candidate_id": cid, "doc_id": "cpc", "start": 0, "end": 10, "header": "Art. 1º",
            "question": "Pergunta?", "category": category}


def _triage(cid, status="judged", cites=False, ngram=1):
    return {"candidate_id": cid, "status": status, "competitors": [], "flagged": False, "flag_reasons": [],
            "signals": {"content_overlap": 0.1, "max_shared_ngram": ngram, "cites_source": cites}}


def _verdict(**change):
    verdict = {"reasoning": "ok", "answerable": "yes", "also_answered_by": [], "leakage": "none",
               "category": "conceito"}
    verdict.update(change)
    return verdict


def _judgment(cid, a=None, b=None, version=RUBRIC_VERSION):
    return {"candidate_id": cid, "rubric_version": version, "judged_at": "2026-09-14",
            "judges": {A: {"verdict": a, "error": None if a else "failed"},
                       B: {"verdict": b, "error": None if b else "failed"}}}


@pytest.mark.parametrize("labels, expected", [
    (["conceito", "conceito", "procedimento"], "conceito"),
    (["conceito", "procedimento", "fato_pontual"], None),
    (["fato_pontual"] * 3, "fato_pontual"),
])
def test_majority_category(labels, expected):
    assert majority_category(labels) == expected


def test_clean_candidate_is_included_with_the_majority_category_and_leakage_signals():
    d = decide(_cand("x", "fato_pontual"), _triage("x"),
               _judgment("x", _verdict(category="procedimento"), _verdict(category="procedimento")))
    assert d.include and d.reasons == [] and d.category == "procedimento"
    assert d.leakage == LeakageSignals(judges={A: "none", B: "none"}, max_shared_ngram=1, no_leakage=True)


@pytest.mark.parametrize("triage_row, a, b, reason", [
    (_triage("x"), _verdict(answerable="partial"), _verdict(), f"answerable:{A}=partial"),
    (_triage("x"), _verdict(), _verdict(also_answered_by=["C1"]), f"also_answered_by:{B}=C1"),
    (_triage("x", cites=True), _verdict(), _verdict(), "cites_source"),
    (_triage("x"), _verdict(), None, f"judge_missing:{B}"),
    (_triage("x"), _verdict(category="procedimento"), _verdict(category="fato_pontual"),
     "category_no_majority:conceito/procedimento/fato_pontual"),
])
def test_each_exclusion_rule(triage_row, a, b, reason):
    d = decide(_cand("x"), triage_row, _judgment("x", a, b))
    assert not d.include and reason in d.reasons


def test_leakage_never_excludes_but_is_recorded():
    d = decide(_cand("x"), _triage("x", ngram=7), _judgment("x", _verdict(leakage="heavy"), _verdict()))
    assert d.include and d.leakage.no_leakage is False and d.leakage.judges[A] == "heavy"


@pytest.mark.parametrize("ngram, no_leakage", [(4, True), (5, False)])
def test_no_leakage_uses_the_shared_ngram_threshold(ngram, no_leakage):
    d = decide(_cand("x"), _triage("x", ngram=ngram), _judgment("x", _verdict(), _verdict()))
    assert d.leakage.no_leakage is no_leakage


def test_assemble_builds_consensus_items_and_refuses_incomplete_inputs():
    candidates = [_cand("x"), _cand("y"), _cand("r")]
    triage = {"x": _triage("x"), "y": _triage("y"), "r": _triage("r", status="refused")}
    judgments = {"x": _judgment("x", _verdict(), _verdict()),
                 "y": _judgment("y", _verdict(answerable="no"), _verdict())}
    items, decisions = assemble(candidates, triage, judgments)
    assert [i.id for i in items] == ["x"]
    assert items[0].review_mode == "judge_consensus" and items[0].reviewed_by == REVIEWER
    assert {d.candidate_id: d.include for d in decisions} == {"r": False, "x": True, "y": False}
    with pytest.raises(ConsensusRefused):
        assemble(candidates, triage, {"x": judgments["x"]})
    with pytest.raises(ConsensusRefused):
        assemble(candidates, triage, {**judgments, "x": _judgment("x", _verdict(), _verdict(), version="v1")})


def test_assemble_refuses_a_candidate_without_a_triage_row():
    candidates = [_cand("x"), _cand("z")]
    triage = {"x": _triage("x")}
    judgments = {"x": _judgment("x", _verdict(), _verdict())}
    with pytest.raises(ConsensusRefused, match=r"z: no triage row, run evals\.groundtruth\.golden\.triage"):
        assemble(candidates, triage, judgments)


def test_agreement_table_uses_only_rows_where_both_verdicts_exist():
    judgments = {"x": _judgment("x", _verdict(), _verdict()), "y": _judgment("y", _verdict(), None)}
    table = agreement_table(judgments)
    assert {row["field"] for row in table} == {"answerable", "also answered by any", "leakage", "category"}
    assert all(row["n"] == 1 for row in table)


def test_report_counts_candidates_not_reason_occurrences():
    candidates = [_cand("x"), _cand("y")]
    triage = {"x": _triage("x"), "y": _triage("y")}
    judgments = {"x": _judgment("x", _verdict(), _verdict()),
                 "y": _judgment("y", _verdict(answerable="no"), _verdict(answerable="partial"))}
    items, decisions = assemble(candidates, triage, judgments)
    text = render_report(decisions, items, agreement_table(judgments))
    assert "| answerable | 1 |" in text and "Included: 1." in text and "No human legal review." in text


def test_golden_item_with_consensus_mode_and_leakage_round_trips(tmp_path):
    item = GoldenItem(id="x", question="q?", category="conceito", passages=[Passage(doc_id="cpc", start=0, end=5)],
                      source_article="cpc Art. 1º", reviewed_by=REVIEWER, reviewed_at="2026-09-14",
                      review_mode="judge_consensus",
                      leakage=LeakageSignals(judges={A: "some", B: "none"}, max_shared_ngram=3, no_leakage=True))
    path = tmp_path / "g.jsonl"
    save_golden([item], path)
    assert load_golden(path) == [item]
