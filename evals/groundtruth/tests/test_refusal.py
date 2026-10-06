"""Task 21 rulings 1 and 2: the offline refusal detector, and its agreement with the two judges.

Everything here is offline. It reads the committed generation/answers.jsonl and
generation/scores.json of the 2026-10-06 run and calls no model.
"""
import json
import re

import pytest

from evals.groundtruth.config import ANSWERS, SCORES
from evals.groundtruth.generation.abstention import RUN_FAILED_LABEL
from evals.groundtruth.generation.refusal import (ANSWER_PREFIX_CHARS, PHRASINGS, count_refusals, detect_refusal,
                                                  judge_agreement, normalize, refusal_counts, row_verdict,
                                                  row_verdicts)
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows

PINNED_NAME = "no_basis_pinned"
BASE_NAME = "no_information_in_base"
DOCUMENTS_NAME = "no_information_in_documents"

# The sentence the Task 20 rule tells the agent to produce, as JuriAI.INSTRUCTIONS words it.
INSTRUCTED_SENTENCE = ("diga ao usuário, com todas as letras, que não encontrou base nos documentos da base de "
                       "conhecimento para responder, e pare por aí.")


@pytest.fixture(scope="module")
def answer_rows() -> list[dict]:
    return read_jsonl_rows(ANSWERS)


@pytest.fixture(scope="module")
def committed_scores() -> dict:
    return json.loads(SCORES.read_text(encoding="utf-8"))


def _answer(rows: list[dict], row_id: str) -> str:
    return next(r["answer"] for r in rows if r["id"] == row_id)


def test_normalize_strips_accents_and_case():
    assert normalize("Não Encontrei INFORMAÇÕES") == "nao encontrei informacoes"


def test_normalize_collapses_whitespace_so_a_reflowed_sentence_still_matches():
    assert normalize("nao encontrei\n  informacoes  na\tbase") == "nao encontrei informacoes na base"


def test_normalize_accepts_an_empty_answer():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_phrasing_names_are_unique():
    names = [name for name, _ in PHRASINGS]
    assert len(names) == len(set(names))


def test_detects_the_phrasing_the_task_20_instruction_pins():
    verdict = detect_refusal("Não encontrou base nos documentos da base de conhecimento para responder.")
    assert verdict.is_refusal is True
    assert verdict.phrasing == PINNED_NAME


def test_detects_the_pinned_phrasing_in_the_first_person_the_agent_would_write():
    verdict = detect_refusal("Não encontrei base na base de conhecimento para responder a essa pergunta.")
    assert verdict.is_refusal is True
    assert verdict.phrasing == PINNED_NAME


def test_detects_the_pinned_phrasing_without_accents():
    verdict = detect_refusal("Nao encontrei base nos documentos da base de conhecimento para responder.")
    assert verdict.is_refusal is True
    assert verdict.phrasing == PINNED_NAME


def test_the_detector_matches_the_sentence_juriai_instructions_asks_for():
    """Binds the two sides: if the instruction's wording moves, this fails rather than the count
    silently dropping to zero."""
    assert detect_refusal(INSTRUCTED_SENTENCE).phrasing == PINNED_NAME


def test_the_instructed_sentence_is_still_the_one_in_juriai_instructions(django_ready):
    from ia.agents import JuriAI

    assert normalize(INSTRUCTED_SENTENCE) in normalize(JuriAI.INSTRUCTIONS)


def test_detects_the_knowledge_base_variant_the_committed_run_produced(answer_rows):
    verdict = detect_refusal(_answer(answer_rows, "oos-05"))
    assert verdict.is_refusal is True
    assert verdict.phrasing == BASE_NAME
    assert verdict.matched_text == "nao encontrei informacoes na base de conhecimento"


def test_detects_the_variant_with_a_qualifier_before_the_base(answer_rows):
    verdict = detect_refusal(_answer(answer_rows, "oos-01"))
    assert verdict.is_refusal is True
    assert verdict.phrasing == BASE_NAME
    assert verdict.matched_text == "nao encontrei informacoes especificas na base de conhecimento"


def test_detects_the_variant_with_a_qualifier_after_the_base(answer_rows):
    """oos-02 and oos-09 put the qualifier after "base de conhecimento", so the phrase itself still
    has to match."""
    for row_id in ("oos-02", "oos-09"):
        verdict = detect_refusal(_answer(answer_rows, row_id))
        assert verdict.is_refusal is True, row_id
        assert verdict.phrasing == BASE_NAME, row_id


def test_detects_the_documents_wording_of_the_same_sentence():
    verdict = detect_refusal("Não encontrei informações específicas nos documentos enviados.")
    assert verdict.is_refusal is True
    assert verdict.phrasing == DOCUMENTS_NAME


def test_a_substantive_answer_is_not_a_refusal(answer_rows):
    verdict = detect_refusal(_answer(answer_rows, "r1-cdc-066"))
    assert verdict.is_refusal is False
    assert verdict.phrasing is None
    assert verdict.matched_text is None


def test_a_clarification_request_that_mentions_the_base_is_not_a_refusal(answer_rows):
    """r1-cpc-016 asks which kind of process the question means and offers to search the base. It
    names the knowledge base but never says it found nothing there."""
    assert detect_refusal(_answer(answer_rows, "r1-cpc-016")).is_refusal is False


def test_a_short_answer_is_not_a_refusal_by_being_short():
    assert detect_refusal("O prazo é de 15 dias.").is_refusal is False


def test_a_long_answer_is_still_a_refusal_when_it_carries_the_phrasing():
    padding = "Recomendo procurar um advogado especializado. " * 40
    answer = "Não encontrei informações na base de conhecimento sobre isso. " + padding
    assert len(answer) > 1000
    assert detect_refusal(answer).is_refusal is True


def test_the_phrase_cannot_be_assembled_across_a_sentence_boundary():
    """The gap inside a phrasing never crosses . ! or ?, so two unrelated sentences do not combine
    into a refusal."""
    answer = "Não encontrei informações sobre a multa. A pesquisa na base de conhecimento segue."
    assert detect_refusal(answer).is_refusal is False


def test_row_verdict_reports_the_matched_phrasing_for_an_audit(answer_rows):
    verdict = row_verdict(next(r for r in answer_rows if r["id"] == "oos-03"))
    assert verdict["id"] == "oos-03"
    assert verdict["is_refusal"] is True
    assert verdict["phrasing"] == BASE_NAME
    assert verdict["matched_text"] == "nao encontrei informacoes na base de conhecimento"
    assert verdict["run_failed"] is False
    assert verdict["answer_prefix"] == _answer(answer_rows, "oos-03")[:ANSWER_PREFIX_CHARS]


def test_a_failed_run_is_never_a_refusal():
    row = {"id": "oos-07", "answer": "Request too large for gpt-4o ... Limit 30000, Requested 40571.",
           "run_failed": True, "usage": {"input_tokens": 0, "output_tokens": 0}, "tool_calls": []}
    verdict = row_verdict(row)
    assert verdict["run_failed"] is True
    assert verdict["is_refusal"] is False
    assert verdict["phrasing"] is None


def test_a_failed_run_is_never_a_refusal_even_when_the_error_text_carries_the_phrasing():
    """Belt and braces: the decision for a failed run does not depend on what its error text says."""
    row = {"id": "oos-07", "answer": "Não encontrei informações na base de conhecimento", "run_failed": True}
    assert row_verdict(row)["is_refusal"] is False


def test_a_legacy_row_without_run_failed_falls_back_to_the_answers_module_rule():
    """The preserved pre-adoption rows carry no run_failed key; is_failed_run's fallback decides."""
    row = {"id": "oos-01", "answer": "Request too large for gpt-4o on tokens per min (TPM): Limit 30000.",
           "usage": {"input_tokens": 0, "output_tokens": 0}, "tool_calls": []}
    assert row_verdict(row)["run_failed"] is True
    assert row_verdict(row)["is_refusal"] is False


def test_count_refusals_counts_only_detected_refusals():
    rows = [{"id": "a", "answer": "Não encontrei informações na base de conhecimento sobre isso.",
             "run_failed": False},
            {"id": "b", "answer": "O prazo é de 15 dias.", "run_failed": False},
            {"id": "c", "answer": "Não encontrou base nos documentos da base de conhecimento.",
             "run_failed": False}]
    assert count_refusals(rows) == 2


def test_row_verdicts_keeps_one_entry_per_row_in_order():
    rows = [{"id": "a", "answer": "x", "run_failed": False}, {"id": "b", "answer": "y", "run_failed": False}]
    assert [v["id"] for v in row_verdicts(rows)] == ["a", "b"]


def test_refusal_counts_splits_golden_from_out_of_scope_by_category():
    rows = [{"id": "g1", "category": "conceito", "answer": "O prazo é de 15 dias.", "run_failed": False},
            {"id": "g2", "category": "conceito",
             "answer": "Não encontrei informações na base de conhecimento sobre isso.", "run_failed": False},
            {"id": "oos-01", "category": "fora_de_escopo",
             "answer": "Não encontrei informações na base de conhecimento sobre isso.", "run_failed": False}]
    assert refusal_counts(rows) == {"n_golden": 2, "n_out_of_scope": 1,
                                    "golden_refusals": 1, "out_of_scope_refusals": 1}


def test_the_committed_run_has_one_refusal_among_the_30_golden_rows(answer_rows):
    counts = refusal_counts(answer_rows)
    assert counts["n_golden"] == 30
    assert counts["golden_refusals"] == 1


def test_the_one_golden_refusal_is_r1_cdc_060(answer_rows):
    golden = [r for r in answer_rows if r["category"] != "fora_de_escopo"]
    refused = [v["id"] for v in row_verdicts(golden) if v["is_refusal"]]
    assert refused == ["r1-cdc-060"]


def test_the_committed_run_abstains_on_all_10_out_of_scope_rows(answer_rows):
    counts = refusal_counts(answer_rows)
    assert counts["n_out_of_scope"] == 10
    assert counts["out_of_scope_refusals"] == 10


def test_the_detector_agrees_with_both_judges_on_every_out_of_scope_row(answer_rows, committed_scores):
    oos = [r for r in answer_rows if r["category"] == "fora_de_escopo"]
    agreement = judge_agreement(oos, committed_scores["abstention"])
    assert agreement["n"] == 10
    assert agreement["agree"] == 10
    assert agreement["disagreements"] == []


def test_judge_agreement_names_a_disagreement_with_the_answer_prefix():
    rows = [{"id": "oos-01", "category": "fora_de_escopo", "answer": "A pena é de 1 a 5 anos de reclusão.",
             "run_failed": False}]
    stored = [{"id": "oos-01", "label": "abstained"}]
    agreement = judge_agreement(rows, stored)
    assert agreement["n"] == 1
    assert agreement["agree"] == 0
    assert agreement["disagreements"] == [{"id": "oos-01", "detector_refusal": False,
                                           "judge_label": "abstained",
                                           "answer_prefix": "A pena é de 1 a 5 anos de reclusão."}]


def test_judge_agreement_treats_a_non_abstained_label_as_not_abstained():
    rows = [{"id": "oos-01", "category": "fora_de_escopo", "answer": "A pena é de 1 a 5 anos.",
             "run_failed": False}]
    for label in ("answered", "disagreement", "unverified", RUN_FAILED_LABEL):
        agreement = judge_agreement(rows, [{"id": "oos-01", "label": label}])
        assert agreement["agree"] == 1, label
        assert agreement["disagreements"] == [], label


def test_judge_agreement_refuses_a_row_with_no_stored_label():
    rows = [{"id": "oos-99", "category": "fora_de_escopo", "answer": "x", "run_failed": False}]
    with pytest.raises(ValueError, match="oos-99"):
        judge_agreement(rows, [])


def test_the_answer_prefix_is_the_first_200_characters():
    assert ANSWER_PREFIX_CHARS == 200


def test_every_phrasing_is_documented_with_a_comment():
    """An auditor reads the module to check a verdict, so each phrasing carries a comment above it."""
    from evals.groundtruth.generation import refusal

    source = refusal.__file__
    text = open(source, encoding="utf-8").read()
    for name, _ in PHRASINGS:
        constant = name.upper()
        match = re.search(rf"^{constant} = ", text, re.MULTILINE)
        assert match, f"{constant} is not a module constant"
        before = text[:match.start()].rstrip().splitlines()[-1]
        assert before.lstrip().startswith("#"), f"{constant} has no comment above it"
