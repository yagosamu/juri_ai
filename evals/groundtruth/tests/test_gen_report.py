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


def _tokens_per_turn(max_tokens=6257, over=0):
    return {"count": 40, "mean": 5479.75, "median": 5640.5, "max": max_tokens,
            "over_tpm_limit": over, "tpm_limit": 30000}


def _failed_rows():
    return [{"id": "oos-01", "question": "q1", "error": "Limit 30000, Requested 40540"}]


def _counts_with_one_failure():
    return {"abstained": 0, "answered": 9, "disagreement": 0, "unverified": 0, "run_failed": 1}


def test_render_report_states_the_tier_1_tpm_limit_note_when_a_run_failed():
    text = render_report(_setup(), _agg(), _abstention_results(), _counts_with_one_failure(), _tool_use(),
                         _usage(), "src", ["l"], failed_rows=_failed_rows(),
                         tokens_per_turn=_tokens_per_turn(max_tokens=40912, over=2))
    assert "30,000 gpt-4o tokens-per-minute" in text
    # Task 20: the note no longer names a chunk size. It was pinned at "5000-character chunks", which
    # became false once production adopted 1500/150; the Setup section states the chunking instead.
    assert "5000-character chunks" not in text
    assert "retrieval config named in Setup above" in text


def test_render_report_blames_one_turn_only_when_a_turn_really_exceeded_the_limit():
    """Task 20 phase 3: the note claimed a single turn can exceed 30000 on its own. True of the
    pre-adoption run, whose largest turn was 40912, and false at 1500/150, where it is 6257."""
    text = render_report(_setup(), _agg(), _abstention_results(), _counts_with_one_failure(), _tool_use(),
                         _usage(), "src", ["l"], failed_rows=_failed_rows(),
                         tokens_per_turn=_tokens_per_turn(max_tokens=40912, over=2))
    assert "on its own" in text
    assert "40912" in text
    assert "paces nothing" not in text


def test_render_report_blames_pacing_when_no_single_turn_came_close():
    text = render_report(_setup(), _agg(), _abstention_results(), _counts_with_one_failure(), _tool_use(),
                         _usage(), "src", ["l"], failed_rows=_failed_rows(),
                         tokens_per_turn=_tokens_per_turn(max_tokens=6257, over=0))
    assert "paces nothing" in text
    assert "6257" in text
    assert "on its own" not in text
    assert "not of the retrieval config being measured" in text


def test_render_report_claims_no_cause_when_tokens_per_turn_was_not_measured():
    text = render_report(_setup(), _agg(), _abstention_results(), _counts_with_one_failure(), _tool_use(),
                         _usage(), "src", ["l"], failed_rows=_failed_rows())
    assert "not determined here" in text
    assert "on its own" not in text
    assert "paces nothing" not in text


def test_render_report_states_no_tpm_cause_at_all_when_no_run_failed():
    """The final 1500/150 run has 0 failed rows, so no explanation of a rate-limit failure belongs
    in it, in either direction."""
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(),
                         _usage(), "src", ["l"], tokens_per_turn=_tokens_per_turn())
    assert "No run failed." in text
    assert "on its own" not in text
    assert "paces nothing" not in text
    assert "not determined here" not in text


def test_render_report_omits_the_judge_usage_on_failed_runs_note_when_nothing_failed():
    """With 0 failed runs no judge call was ever made on an error string, so the note describes
    calls that do not exist."""
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(),
                         _usage(), "src", ["l"], tokens_per_turn=_tokens_per_turn())
    assert "includes calls made on failed runs" not in text


def test_render_report_keeps_the_judge_usage_on_failed_runs_note_when_a_run_failed():
    text = render_report(_setup(), _agg(), _abstention_results(), _counts_with_one_failure(), _tool_use(),
                         _usage(), "src", ["l"], failed_rows=_failed_rows(),
                         tokens_per_turn=_tokens_per_turn())
    assert "includes calls made on failed runs" in text


def test_render_report_has_a_tokens_per_turn_section_with_the_measured_numbers():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(),
                         _usage(), "src", ["l"], tokens_per_turn=_tokens_per_turn())
    section = text.split("## Tokens per turn")[1].split("## ")[0]
    assert "40" in section
    assert "5479.8" in section or "5479.75" in section
    assert "6257" in section
    assert "30000" in section


def test_render_report_omits_the_tokens_per_turn_section_when_not_measured():
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(),
                         _usage(), "src", ["l"])
    assert "## Tokens per turn" not in text


def test_render_report_states_the_unscored_counts_and_their_reason():
    agg = _agg()
    agg["unscored_faithfulness"] = 1
    agg["unscored_relevancy"] = 0
    agg["unscored_reasons"] = {"content_filter": 1}
    text = render_report(_setup(), agg, _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    section = text.split("## Faithfulness and relevancy")[1].split("## Abstention")[0]
    assert "Not scored by the judge, excluded from that metric's mean: faithfulness 1, relevancy 0." in section
    assert "content_filter 1" in section


def test_render_report_states_zero_unscored_rather_than_staying_silent():
    """A mean over fewer cases must never be published without the reader being told, so the line is
    printed even when nothing was excluded."""
    agg = _agg()
    agg["unscored_faithfulness"] = 0
    agg["unscored_relevancy"] = 0
    agg["unscored_reasons"] = {}
    text = render_report(_setup(), agg, _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "Not scored by the judge, excluded from that metric's mean: faithfulness 0, relevancy 0." in text


def test_render_report_treats_an_agg_without_the_unscored_keys_as_zero():
    """A legacy scores.json rendered by --report-only has no unscored keys at all."""
    text = render_report(_setup(), _agg(), _abstention_results(), _abstention_counts(), _tool_use(), _usage(),
                         "src", ["l"])
    assert "Not scored by the judge, excluded from that metric's mean: faithfulness 0, relevancy 0." in text


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
