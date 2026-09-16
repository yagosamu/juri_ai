import pytest

from evals.groundtruth.generation.cost import total_cost
from evals.groundtruth.generation.gen_report import MEMORY_UPDATE_COST_NOTE, parse_tpm_error, render_report


def _setup():
    return {"agent_model": "gpt-4o (agno default)", "retrieval_config": "production (5000/0 dense)",
           "seed": 7, "sampled_golden_ids": ["g-01", "g-02"],
           "sampled_oos_ids": [f"oos-{n:02d}" for n in range(1, 11)],
           "deepeval_model": "gpt-4.1-mini", "deepeval_version": "3.9.9",
           "abstention_judges": ["gpt-4.1", "claude-haiku-4-5"]}


def _agg():
    return {"by_category": {"conceito": {"faithfulness": {"mean": 0.8, "n": 1}, "relevancy": {"mean": 0.9, "n": 2}}},
           "overall": {"faithfulness": {"mean": 0.8, "n": 1}, "relevancy": {"mean": 0.9, "n": 2}},
           "no_retrieval": 1, "run_failed": 0}


def _abstention_results():
    return [{"id": f"oos-{n:02d}", "question": f"q{n}", "label": "abstained"} for n in range(1, 11)]


def _abstention_counts():
    return {"abstained": 8, "answered": 1, "disagreement": 1, "unverified": 0, "run_failed": 0}


def _usage():
    return {"gpt-4o": {"input_tokens": 1000, "output_tokens": 500},
           "gpt-4.1-mini": {"input_tokens": 200, "output_tokens": 100}}


def _tool_use():
    return {"searched": 9, "datajud_called": 0, "total": 10}


def test_render_report_has_every_required_section():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "test price source", ["limitation one", "limitation two"])
    for heading in ("## Setup", "## Faithfulness and relevancy", "## Abstention", "## Failed runs", "## Tool use",
                    "## Measured cost per model", "## Limitations"):
        assert heading in text


def test_render_report_counts_are_right():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "Abstained: 8 of 10 completed runs." in text
    assert "Answered: 1 of 10 completed runs." in text
    assert "Disagreement: 1 of 10 completed runs." in text
    assert "Unverified: 0 of 10 completed runs." in text
    assert "Run failed: 0 of 10 out-of-scope questions." in text
    assert "No retrieval, excluded from the faithfulness mean: 1." in text
    assert "Answers that searched the knowledge base: 9 of 10." in text
    assert "Answers that called DataJud: 0 of 10." in text


def test_render_report_lists_every_sampled_id_and_abstention_row():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "g-01" in text and "g-02" in text
    for row in _abstention_results():
        assert row["id"] in text


def test_render_report_cost_matches_recorded_prices():
    usage = _usage()
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), usage,
                         "src", ["l"])
    expected = total_cost(usage)
    assert f"{expected:.4f}" in text


def test_render_report_includes_price_source():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "distinctive price source marker", ["l"])
    assert "distinctive price source marker" in text


def test_render_report_includes_extra_costs_in_the_total():
    usage = _usage()
    extra = {"gpt-4.1-mini": 0.0123}
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), usage,
                         "src", ["l"], extra_costs=extra)
    expected = total_cost(usage) + 0.0123
    assert f"{expected:.4f}" in text
    assert "0.0123" in text


def test_render_report_always_states_the_unmetered_memory_update_cost():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert MEMORY_UPDATE_COST_NOTE in text
    assert text.count(MEMORY_UPDATE_COST_NOTE) == 1  # appears once in the cost section; callers repeat it below


def test_render_report_has_no_em_dash():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "—" not in text


def test_render_report_lists_limitations():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["Both scorers are LLM judges.", "There is no human legal review."])
    assert "- Both scorers are LLM judges." in text
    assert "- There is no human legal review." in text


# --- Fix round 1: failed runs -----------------------------------------------------

def test_parse_tpm_error_extracts_limit_and_requested():
    message = ("Request too large for gpt-4o in organization org-x on tokens per min (TPM): Limit 30000, "
              "Requested 40571. The input or output tokens must be reduced.")
    assert parse_tpm_error(message) == {"limit": 30000, "requested": 40571}


def test_parse_tpm_error_returns_none_for_an_unrelated_message():
    assert parse_tpm_error("some other error") is None
    assert parse_tpm_error("") is None


def test_render_report_states_no_run_failed_when_failed_rows_is_empty():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "No run failed." in text


def test_render_report_lists_failed_rows_with_parsed_tpm_numbers():
    failed_rows = [{"id": "oos-01", "question": "q1",
                    "error": "... TPM: Limit 30000, Requested 40540. ..."},
                   {"id": "oos-07", "question": "q7",
                    "error": "... TPM: Limit 30000, Requested 40571. ..."}]
    counts = {"abstained": 0, "answered": 7, "disagreement": 0, "unverified": 0, "run_failed": 2}
    text = render_report(_setup(), _agg(), _abstention_results(), counts, _tool_use(), _usage(), "src", ["l"],
                         failed_rows=failed_rows)
    assert "oos-01" in text.split("## Failed runs")[1].split("## Tool use")[0]
    assert "30000" in text
    assert "40540" in text
    assert "40571" in text
    assert "Run failed: 2 of 9 out-of-scope questions." in text
    assert "Abstained: 0 of 7 completed runs." in text
    assert "Answered: 7 of 7 completed runs." in text


def test_render_report_parses_tpm_numbers_from_a_legacy_row_with_no_error_field():
    # A row written before fix round 1 has no "error" key, only "answer" carrying the same text.
    failed_rows = [{"id": "oos-01", "question": "q1", "answer": "... Limit 30000, Requested 40540. ..."}]
    counts = {"abstained": 0, "answered": 9, "disagreement": 0, "unverified": 0, "run_failed": 1}
    text = render_report(_setup(), _agg(), _abstention_results(), counts, _tool_use(), _usage(), "src", ["l"],
                         failed_rows=failed_rows)
    assert "30000" in text.split("## Failed runs")[1].split("## Tool use")[0]
    assert "40540" in text


def test_render_report_states_the_tier_1_tpm_limit_note_when_a_run_failed():
    failed_rows = [{"id": "oos-01", "question": "q1", "error": "Limit 30000, Requested 40540"}]
    counts = {"abstained": 0, "answered": 9, "disagreement": 0, "unverified": 0, "run_failed": 1}
    text = render_report(_setup(), _agg(), _abstention_results(), counts, _tool_use(), _usage(), "src", ["l"],
                         failed_rows=failed_rows)
    assert "30,000 tokens-per-minute" in text
    assert "5000-character chunks" in text


def test_render_report_states_faithfulness_unchanged_when_no_golden_run_failed():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "No golden run failed, so faithfulness and relevancy are unchanged" in text


def test_render_report_omits_the_unchanged_claim_when_a_golden_run_failed():
    agg = _agg()
    agg["run_failed"] = 1
    text = render_report(_setup(), agg, _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "Run failed, excluded from both means: 1." in text
    assert "No golden run failed" not in text
