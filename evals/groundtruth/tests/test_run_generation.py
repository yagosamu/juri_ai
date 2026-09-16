"""Only the pure helpers of run_generation are tested here: importing this module must never touch
Django, ia.agents or ia.tasks, and none of these tests call main() with a real Django/agent path.
run_report_only is exercised directly (with monkeypatched file paths) because it makes no API call
either, so it is safe and cheap to test for real, per fix round 1 ruling 3."""
import json
import os
from types import SimpleNamespace

import pytest

from evals.groundtruth.generation import run_generation as rg
from evals.groundtruth.generation.gen_report import MEMORY_UPDATE_COST_NOTE
from evals.groundtruth.generation.run_generation import (abstention_judge_usage, apply_limits, build_arg_parser,
                                                          build_limitations, configure_environment,
                                                          deepeval_cost_total, failed_rows_of, generate_answers,
                                                          merge_scores, partition_selected, replace_rows,
                                                          select_only_ids, split_by_kind, tool_use_summary,
                                                          usage_total, write_jsonl)


# --- CLI ----------------------------------------------------------------------

def test_build_arg_parser_defaults_to_no_limits_and_no_smoke():
    args = build_arg_parser().parse_args([])
    assert args.limit_golden is None
    assert args.limit_oos is None
    assert args.smoke is False


def test_build_arg_parser_reads_limit_and_smoke_flags():
    args = build_arg_parser().parse_args(["--limit-golden", "1", "--limit-oos", "2", "--smoke"])
    assert args.limit_golden == 1
    assert args.limit_oos == 2
    assert args.smoke is True


def test_build_arg_parser_reads_report_only_flag():
    args = build_arg_parser().parse_args(["--report-only"])
    assert args.report_only is True
    assert args.only is None


def test_build_arg_parser_reads_only_flag_with_multiple_ids():
    args = build_arg_parser().parse_args(["--only", "oos-01", "oos-07", "oos-08"])
    assert args.only == ["oos-01", "oos-07", "oos-08"]
    assert args.report_only is False


# --- main() dispatch (no Django touched for --report-only / --only) ---------------

def test_main_dispatches_report_only_before_touching_django(monkeypatch):
    calls = []
    monkeypatch.setattr(rg, "run_report_only", lambda: calls.append("called") or {"ok": True})
    result = rg.main(["--report-only"])
    assert calls == ["called"]
    assert result == {"ok": True}


def test_main_dispatches_only_before_touching_django(monkeypatch):
    calls = []
    monkeypatch.setattr(rg, "run_only", lambda ids: calls.append(ids) or {"ok": True})
    result = rg.main(["--only", "oos-01", "oos-07"])
    assert calls == [["oos-01", "oos-07"]]
    assert result == {"ok": True}


# --- Partitioning and limits ----------------------------------------------------

def _selected():
    return ([{"id": f"g-{i:02d}", "kind": "golden"} for i in range(3)] +
            [{"id": f"oos-{i:02d}", "kind": "out_of_scope"} for i in range(2)])


def test_partition_selected_splits_by_kind_and_keeps_order():
    golden, oos = partition_selected(_selected())
    assert [g["id"] for g in golden] == ["g-00", "g-01", "g-02"]
    assert [o["id"] for o in oos] == ["oos-00", "oos-01"]


def test_apply_limits_caps_each_list_independently():
    golden, oos = partition_selected(_selected())
    limited_golden, limited_oos = apply_limits(golden, oos, limit_golden=1, limit_oos=1)
    assert len(limited_golden) == 1 and len(limited_oos) == 1


def test_apply_limits_none_means_no_cap():
    golden, oos = partition_selected(_selected())
    limited_golden, limited_oos = apply_limits(golden, oos, limit_golden=None, limit_oos=None)
    assert len(limited_golden) == 3 and len(limited_oos) == 2


# --- Aggregation helpers ---------------------------------------------------------

def test_tool_use_summary_counts_searched_and_datajud():
    rows = [{"searched": True, "datajud_called": False}, {"searched": True, "datajud_called": True},
            {"searched": False, "datajud_called": False}]
    assert tool_use_summary(rows) == {"searched": 2, "datajud_called": 1, "total": 3}


def test_usage_total_sums_input_and_output_tokens():
    rows = [{"usage": {"input_tokens": 10, "output_tokens": 5}}, {"usage": {"input_tokens": 20, "output_tokens": 7}}]
    assert usage_total(rows) == {"input_tokens": 30, "output_tokens": 12}


def test_abstention_judge_usage_sums_only_the_named_judge():
    results = [
        {"judges": {"gpt-4.1": {"usage": {"input_tokens": 10, "output_tokens": 2}}, "claude-haiku-4-5": {
            "usage": {"input_tokens": 8, "output_tokens": 1}}}},
        {"judges": {"gpt-4.1": {"usage": {"input_tokens": 5, "output_tokens": 1}}, "claude-haiku-4-5": {
            "usage": None}}},
    ]
    assert abstention_judge_usage(results, "gpt-4.1") == {"input_tokens": 15, "output_tokens": 3}
    assert abstention_judge_usage(results, "claude-haiku-4-5") == {"input_tokens": 8, "output_tokens": 1}


def test_deepeval_cost_total_sums_relevancy_and_faithfulness_costs():
    scored = [{"relevancy_cost": 0.001, "faithfulness_cost": 0.002}, {"relevancy_cost": 0.0005,
             "faithfulness_cost": None}]
    assert deepeval_cost_total(scored) == 0.001 + 0.002 + 0.0005


def test_build_limitations_includes_the_memory_update_cost_note_verbatim():
    assert MEMORY_UPDATE_COST_NOTE in build_limitations()


# --- File writing -----------------------------------------------------------------

def test_write_jsonl_writes_one_json_object_per_line(tmp_path):
    path = tmp_path / "sub" / "answers.jsonl"
    write_jsonl([{"a": 1}, {"b": "café"}], path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"b": "café"}]


# --- Environment configuration ----------------------------------------------------

def test_configure_environment_points_the_agent_stores_at_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("LANCEDB_URI", raising=False)
    monkeypatch.delenv("AGNO_MEMORY_DB_FILE", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    configure_environment(tmp_path)
    assert os.environ["DATA_DIR"] == str(tmp_path)
    assert os.environ["LANCEDB_URI"] == str(tmp_path / "lancedb")
    assert os.environ["AGNO_MEMORY_DB_FILE"] == str(tmp_path / "agno_memory.sqlite3")
    assert os.environ["SECRET_KEY"]


def test_configure_environment_does_not_override_an_existing_secret_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "already-set")
    configure_environment(tmp_path)
    assert os.environ["SECRET_KEY"] == "already-set"


def test_configure_environment_always_forces_lancedb_uri_into_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LANCEDB_URI", "C:/somewhere/else/lancedb")
    configure_environment(tmp_path)
    assert os.environ["LANCEDB_URI"] == str(tmp_path / "lancedb")


# --- Answer generation with a fake agent (no Django, no agno) ---------------------

class FakeRun:
    def __init__(self, content, tools=None, usage=(1, 1)):
        self.content = content
        self.tools = tools or []
        self.metrics = SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1])


class FakeAgent:
    def __init__(self, run):
        self._run = run
        self.ran_with = None

    def run(self, question):
        self.ran_with = question
        return self._run


class FakeJuriAI:
    """Stands in for ia.agents.JuriAI: MEMORY_DB_FILE is a class-attribute-like slot build_agent reads."""

    def __init__(self):
        self.MEMORY_DB_FILE = None
        self.build_agent_calls = []

    def build_agent(self, knowledge_filters):
        self.build_agent_calls.append({"knowledge_filters": knowledge_filters, "memory_db_file": self.MEMORY_DB_FILE})
        return FakeAgent(FakeRun("resposta", tools=[]))


def test_generate_answers_sets_a_fresh_memory_path_before_each_run(tmp_path):
    juri_ai = FakeJuriAI()
    items = [{"id": "g-01", "question": "q1", "category": "conceito"},
            {"id": "g-02", "question": "q2", "category": "conceito"}]
    rows = generate_answers(items, juri_ai, tmp_path)
    assert len(rows) == 2
    memory_files = [call["memory_db_file"] for call in juri_ai.build_agent_calls]
    assert memory_files[0] != memory_files[1]
    assert memory_files[0].endswith("g-01.sqlite3")
    assert memory_files[1].endswith("g-02.sqlite3")


def test_generate_answers_passes_the_tenant_as_knowledge_filter(tmp_path):
    juri_ai = FakeJuriAI()
    items = [{"id": "g-01", "question": "q1", "category": "conceito"}]
    generate_answers(items, juri_ai, tmp_path, tenant=7)
    assert juri_ai.build_agent_calls[0]["knowledge_filters"] == {"cliente_id": 7}


def test_generate_answers_builds_one_row_per_item_in_order(tmp_path):
    juri_ai = FakeJuriAI()
    items = [{"id": "g-01", "question": "q1", "category": "conceito"},
            {"id": "oos-01", "question": "q2", "category": "fora_de_escopo"}]
    rows = generate_answers(items, juri_ai, tmp_path)
    assert [r["id"] for r in rows] == ["g-01", "oos-01"]
    assert all(r["answer"] == "resposta" for r in rows)


# --- Fix round 1: failed-run helpers -----------------------------------------------

def test_failed_rows_of_filters_using_is_failed_run():
    rows = [{"id": "a", "run_failed": False}, {"id": "b", "run_failed": True}]
    assert [r["id"] for r in failed_rows_of(rows)] == ["b"]


def test_split_by_kind_separates_golden_from_out_of_scope_and_keeps_order():
    rows = [{"id": "g-01", "category": "conceito"}, {"id": "oos-01", "category": "fora_de_escopo"},
            {"id": "g-02", "category": "procedimento"}]
    golden, oos = split_by_kind(rows)
    assert [r["id"] for r in golden] == ["g-01", "g-02"]
    assert [r["id"] for r in oos] == ["oos-01"]


def test_select_only_ids_returns_the_named_failed_rows_in_the_given_order():
    rows = [{"id": "oos-01", "run_failed": True}, {"id": "oos-02", "run_failed": False},
            {"id": "oos-07", "run_failed": True}]
    selected = select_only_ids(rows, ["oos-07", "oos-01"])
    assert [r["id"] for r in selected] == ["oos-07", "oos-01"]


def test_select_only_ids_refuses_an_id_that_is_not_currently_failed():
    rows = [{"id": "oos-02", "run_failed": False}]
    with pytest.raises(ValueError):
        select_only_ids(rows, ["oos-02"])


def test_select_only_ids_refuses_an_unknown_id():
    with pytest.raises(ValueError):
        select_only_ids([], ["oos-99"])


def test_replace_rows_swaps_matching_ids_in_place_and_keeps_the_rest():
    all_rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}, {"id": "c", "v": 3}]
    new_rows = [{"id": "b", "v": 99}]
    result = replace_rows(all_rows, new_rows)
    assert result == [{"id": "a", "v": 1}, {"id": "b", "v": 99}, {"id": "c", "v": 3}]


def test_replace_rows_appends_a_new_row_not_already_present():
    result = replace_rows([{"id": "a"}], [{"id": "z"}])
    assert [r["id"] for r in result] == ["a", "z"]


def test_merge_scores_replaces_matching_ids_and_keeps_everything_else():
    # Fix round 2 ruling 1: merge_scores only merges the per-item "golden"/"abstention" lists. Any
    # top-level aggregate it leaves untouched (usage_by_model, deepeval_cost_usd, ...) is informational
    # only, since no code path reads it back; the report always recomputes from per-item data instead
    # (see test_run_report_only_ignores_poisoned_stored_aggregates below).
    stored = {"golden": [{"id": "g-01", "faithfulness_score": 0.5}],
             "abstention": [{"id": "oos-01", "label": "answered"}]}
    new_golden = [{"id": "g-02", "faithfulness_score": 0.9}]
    new_abstention = [{"id": "oos-01", "label": "run_failed"}]
    merged = merge_scores(stored, new_golden, new_abstention)
    assert {g["id"] for g in merged["golden"]} == {"g-01", "g-02"}
    assert [a for a in merged["abstention"] if a["id"] == "oos-01"][0]["label"] == "run_failed"


def test_merge_scores_carries_the_replaced_abstention_items_usage_as_prior_attempts():
    # Fix round 2 ruling: Part 2 keeps earlier spend.
    stored = {"golden": [], "abstention": [
        {"id": "oos-01", "label": "run_failed",
         "judges": {"gpt-4.1": {"usage": {"input_tokens": 267, "output_tokens": 62}}}}]}
    new_abstention = [{"id": "oos-01", "label": "abstained",
                       "judges": {"gpt-4.1": {"usage": {"input_tokens": 10, "output_tokens": 4}}}}]
    merged = merge_scores(stored, [], new_abstention)
    oos01 = merged["abstention"][0]
    assert oos01["label"] == "abstained"
    assert oos01["prior_attempts"] == [{"judges_usage": {"gpt-4.1": {"input_tokens": 267, "output_tokens": 62}}}]


def test_merge_scores_carries_the_replaced_golden_items_deepeval_cost_as_prior_attempts():
    stored = {"golden": [{"id": "g-01", "relevancy_cost": 0.001, "faithfulness_cost": 0.002}], "abstention": []}
    new_golden = [{"id": "g-01", "relevancy_cost": 0.0005, "faithfulness_cost": 0.0007}]
    merged = merge_scores(stored, new_golden, [])
    g01 = merged["golden"][0]
    assert g01["prior_attempts"] == [{"deepeval_cost": 0.003}]


def test_merge_scores_accumulates_prior_attempts_across_more_than_one_rerun():
    stored = {"golden": [], "abstention": [
        {"id": "oos-01", "label": "run_failed", "judges": {},
         "prior_attempts": [{"judges_usage": {"gpt-4.1": {"input_tokens": 100, "output_tokens": 10}}}]}]}
    new_abstention = [{"id": "oos-01", "label": "run_failed", "judges": {}}]
    merged = merge_scores(stored, [], new_abstention)
    # The replaced item made no paid call, so it adds no entry of its own; the earlier entry is carried.
    assert merged["abstention"][0]["prior_attempts"] == [
        {"judges_usage": {"gpt-4.1": {"input_tokens": 100, "output_tokens": 10}}}]


def test_merge_scores_does_not_add_prior_attempts_for_a_brand_new_id():
    merged = merge_scores({"golden": [], "abstention": []}, [], [{"id": "oos-05", "label": "answered",
                                                                  "judges": {}}])
    assert "prior_attempts" not in merged["abstention"][0]


def test_replace_rows_attaches_prior_usage_when_the_old_row_had_nonzero_usage():
    all_rows = [{"id": "oos-01", "usage": {"input_tokens": 15, "output_tokens": 4}}]
    new_rows = [{"id": "oos-01", "usage": {"input_tokens": 50, "output_tokens": 12}}]
    result = replace_rows(all_rows, new_rows)
    assert result[0]["prior_usage"] == [{"input_tokens": 15, "output_tokens": 4}]


def test_replace_rows_does_not_attach_prior_usage_when_the_old_row_had_zero_usage():
    all_rows = [{"id": "oos-01", "usage": {"input_tokens": 0, "output_tokens": 0}}]
    new_rows = [{"id": "oos-01", "usage": {"input_tokens": 50, "output_tokens": 12}}]
    result = replace_rows(all_rows, new_rows)
    assert "prior_usage" not in result[0]


def test_usage_total_adds_prior_usage_entries():
    rows = [{"usage": {"input_tokens": 50, "output_tokens": 12}, "prior_usage": [{"input_tokens": 15,
             "output_tokens": 4}]}]
    assert usage_total(rows) == {"input_tokens": 65, "output_tokens": 16}


def test_abstention_judge_usage_adds_prior_attempts_for_the_named_judge():
    results = [{"judges": {"gpt-4.1": {"usage": {"input_tokens": 10, "output_tokens": 4}}},
               "prior_attempts": [{"judges_usage": {"gpt-4.1": {"input_tokens": 267, "output_tokens": 62}}}]}]
    assert abstention_judge_usage(results, "gpt-4.1") == {"input_tokens": 277, "output_tokens": 66}


def test_deepeval_cost_total_adds_prior_attempts_deepeval_cost():
    scored = [{"relevancy_cost": 0.001, "faithfulness_cost": 0.002,
              "prior_attempts": [{"deepeval_cost": 0.005}]}]
    assert deepeval_cost_total(scored) == pytest.approx(0.008)


def test_replace_rows_keeps_unchanged_rows_in_original_order_and_equal_content():
    # Fix round 2 ruling 3: byte-for-byte preservation is not required, but row order must stay stable
    # and an unchanged row must still parse to an equal dict.
    all_rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}, {"id": "c", "v": 3}]
    new_rows = [{"id": "b", "v": 99}]
    result = replace_rows(all_rows, new_rows)
    assert [r["id"] for r in result] == ["a", "b", "c"]
    assert result[0] == all_rows[0]
    assert result[2] == all_rows[2]


def test_write_jsonl_then_read_jsonl_rows_preserves_order_and_dict_equality(tmp_path):
    from evals.groundtruth.golden.jsonl_io import read_jsonl_rows
    rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}, {"id": "c", "v": 3}]
    path = tmp_path / "answers.jsonl"
    write_jsonl(rows, path)
    assert read_jsonl_rows(path) == rows


# --- Fix round 3 finding B: prior_usage/prior_attempts survive a zero-usage middle rerun -----------

def test_replace_rows_keeps_the_first_attempts_usage_through_a_zero_usage_middle_rerun():
    # attempt1 has real usage; attempt2 (a failed rerun) replaces it with zero usage; attempt3 replaces
    # attempt2. attempt1's usage must still be there after both replacements, even though attempt2's own
    # usage was zero and contributed nothing of its own to carry forward.
    attempt1 = [{"id": "oos-01", "usage": {"input_tokens": 100, "output_tokens": 20}}]
    attempt2 = [{"id": "oos-01", "usage": {"input_tokens": 0, "output_tokens": 0}}]
    after_first_replace = replace_rows(attempt1, attempt2)
    attempt3 = [{"id": "oos-01", "usage": {"input_tokens": 50, "output_tokens": 10}}]
    after_second_replace = replace_rows(after_first_replace, attempt3)
    final = after_second_replace[0]
    assert final["prior_usage"] == [{"input_tokens": 100, "output_tokens": 20}]
    assert usage_total([final]) == {"input_tokens": 150, "output_tokens": 30}


def test_replace_rows_counts_every_attempts_usage_exactly_once_when_all_are_nonzero():
    attempt1 = [{"id": "oos-01", "usage": {"input_tokens": 100, "output_tokens": 20}}]
    attempt2 = [{"id": "oos-01", "usage": {"input_tokens": 30, "output_tokens": 5}}]
    after_first_replace = replace_rows(attempt1, attempt2)
    attempt3 = [{"id": "oos-01", "usage": {"input_tokens": 50, "output_tokens": 10}}]
    after_second_replace = replace_rows(after_first_replace, attempt3)
    final = after_second_replace[0]
    assert usage_total([final]) == {"input_tokens": 180, "output_tokens": 35}


def test_merge_scores_keeps_the_first_attempts_spend_through_a_zero_usage_middle_rerun():
    # Same scenario as the replace_rows tests above, for abstention score items' prior_attempts: attempt1
    # has real judge usage; attempt2 (a failed rerun, no judges called) replaces it; attempt3 replaces
    # attempt2. attempt1's spend must survive both merges.
    attempt1_stored = {"golden": [], "abstention": [
        {"id": "oos-01", "label": "answered",
         "judges": {"gpt-4.1": {"usage": {"input_tokens": 267, "output_tokens": 62}}}}]}
    attempt2 = [{"id": "oos-01", "label": "run_failed", "judges": {}}]
    after_first_merge = merge_scores(attempt1_stored, [], attempt2)
    attempt3 = [{"id": "oos-01", "label": "answered",
                "judges": {"gpt-4.1": {"usage": {"input_tokens": 15, "output_tokens": 4}}}}]
    after_second_merge = merge_scores(after_first_merge, [], attempt3)
    final = after_second_merge["abstention"][0]
    assert abstention_judge_usage([final], "gpt-4.1") == {"input_tokens": 282, "output_tokens": 66}
    # The zero-spend middle attempt is not recorded as an attempt of its own.
    assert final["prior_attempts"] == [{"judges_usage": {"gpt-4.1": {"input_tokens": 267, "output_tokens": 62}}}]


def test_merge_scores_omits_a_zero_cost_golden_attempt_from_prior_attempts():
    attempt1_stored = {"golden": [{"id": "g-01", "relevancy_cost": 0.001, "faithfulness_cost": 0.002}],
                       "abstention": []}
    attempt2 = [{"id": "g-01", "relevancy_cost": 0.0, "faithfulness_cost": None}]
    after_first_merge = merge_scores(attempt1_stored, attempt2, [])
    attempt3 = [{"id": "g-01", "relevancy_cost": 0.0001, "faithfulness_cost": 0.0002}]
    final = merge_scores(after_first_merge, attempt3, [])["golden"][0]
    assert final["prior_attempts"] == [{"deepeval_cost": pytest.approx(0.003)}]
    assert deepeval_cost_total([final]) == pytest.approx(0.003 + 0.0003)


def test_merge_scores_counts_every_attempts_spend_exactly_once_when_all_are_nonzero():
    attempt1_stored = {"golden": [{"id": "g-01", "relevancy_cost": 0.001, "faithfulness_cost": 0.002}],
                       "abstention": []}
    attempt2 = [{"id": "g-01", "relevancy_cost": 0.0003, "faithfulness_cost": 0.0004}]
    after_first_merge = merge_scores(attempt1_stored, attempt2, [])
    attempt3 = [{"id": "g-01", "relevancy_cost": 0.0001, "faithfulness_cost": 0.0002}]
    after_second_merge = merge_scores(after_first_merge, attempt3, [])
    final = after_second_merge["golden"][0]
    assert deepeval_cost_total([final]) == pytest.approx(0.001 + 0.002 + 0.0003 + 0.0004 + 0.0001 + 0.0002)


# --- Fix round 1: run_report_only, no API call, safe to run for real -------------

def _fixture_answers():
    return [
        {"id": "g-01", "question": "q1", "category": "conceito", "answer": "a1", "run_failed": False,
         "usage": {"input_tokens": 10, "output_tokens": 5}, "tool_calls": ["search_knowledge_base"],
         "searched": True, "datajud_called": False, "contexts": ["ctx"]},
        {"id": "oos-01", "question": "qo1", "category": "fora_de_escopo", "answer": "rate limit error text",
         "run_failed": True, "error": "Request too large ... Limit 30000, Requested 40540. ...",
         "usage": {"input_tokens": 0, "output_tokens": 0}, "tool_calls": [], "searched": False,
         "datajud_called": False, "contexts": []},
        {"id": "oos-02", "question": "qo2", "category": "fora_de_escopo", "answer": "a2", "run_failed": False,
         "usage": {"input_tokens": 20, "output_tokens": 3}, "tool_calls": ["search_knowledge_base"],
         "searched": True, "datajud_called": False, "contexts": ["ctx"]},
    ]


def _fixture_stored():
    return {
        "golden": [{"id": "g-01", "category": "conceito", "no_retrieval": False, "run_failed": False,
                   "faithfulness_score": 0.9, "faithfulness_reason": "ok", "faithfulness_cost": 0.001,
                   "relevancy_score": 0.8, "relevancy_reason": "ok", "relevancy_cost": 0.001}],
        "faithfulness_relevancy": {
            "by_category": {"conceito": {"faithfulness": {"mean": 0.9, "n": 1}, "relevancy": {"mean": 0.8, "n": 1}}},
            "overall": {"faithfulness": {"mean": 0.9, "n": 1}, "relevancy": {"mean": 0.8, "n": 1}},
            "no_retrieval": 0, "run_failed": 0},
        "abstention": [
            {"id": "oos-01", "question": "qo1", "judges": {
                "gpt-4.1": {"verdict": {"abstained": "no"}, "error": None,
                           "usage": {"input_tokens": 5, "output_tokens": 2}},
                "claude-haiku-4-5": {"verdict": {"abstained": "no"}, "error": None,
                                     "usage": {"input_tokens": 5, "output_tokens": 2}}}, "label": "answered"},
            {"id": "oos-02", "question": "qo2", "judges": {
                "gpt-4.1": {"verdict": {"abstained": "no"}, "error": None,
                           "usage": {"input_tokens": 5, "output_tokens": 2}},
                "claude-haiku-4-5": {"verdict": {"abstained": "no"}, "error": None,
                                     "usage": {"input_tokens": 5, "output_tokens": 2}}}, "label": "answered"},
        ],
        "abstention_counts": {"abstained": 0, "answered": 2, "disagreement": 0, "unverified": 0},
        "usage_by_model": {"gpt-4o": {"input_tokens": 30, "output_tokens": 8},
                          "gpt-4.1": {"input_tokens": 10, "output_tokens": 4},
                          "claude-haiku-4-5": {"input_tokens": 10, "output_tokens": 4}},
        "deepeval_cost_usd": 0.002,
    }


def _write_fixtures(tmp_path, monkeypatch, stored=None):
    answers_path = tmp_path / "answers.jsonl"
    scores_path = tmp_path / "scores.json"
    report_path = tmp_path / "generation.md"
    with answers_path.open("w", encoding="utf-8") as f:
        for row in _fixture_answers():
            f.write(json.dumps(row) + "\n")
    scores_path.write_text(json.dumps(stored if stored is not None else _fixture_stored()), encoding="utf-8")
    monkeypatch.setattr(rg, "ANSWERS", answers_path)
    monkeypatch.setattr(rg, "SCORES", scores_path)
    monkeypatch.setattr(rg, "GENERATION_REPORT", report_path)
    return answers_path, scores_path, report_path


def test_run_report_only_makes_no_api_call_and_rewrites_the_report(tmp_path, monkeypatch):
    _answers_path, _scores_path, report_path = _write_fixtures(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    result = rg.run_report_only()

    assert result["abstention_counts"] == {"abstained": 0, "answered": 1, "disagreement": 0, "unverified": 0,
                                           "run_failed": 1}
    assert result["failed_ids"] == ["oos-01"]
    assert result["faithfulness_relevancy"]["overall"] == _fixture_stored()["faithfulness_relevancy"]["overall"]
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "oos-01" in text
    assert "30000" in text and "40540" in text
    assert "No golden run failed" in text


def test_run_report_only_ignores_poisoned_stored_aggregates(tmp_path, monkeypatch):
    """Fix round 2 ruling 1: the report never reads a stored aggregate. Every top-level aggregate field
    in scores.json is seeded with an obviously wrong sentinel value; the recomputed result and the
    rendered text must both ignore it and reflect only the real per-row data."""
    stored = _fixture_stored()
    stored["usage_by_model"] = {"gpt-4o": {"input_tokens": 999999, "output_tokens": 999999},
                                "gpt-4.1": {"input_tokens": 999999, "output_tokens": 999999},
                                "claude-haiku-4-5": {"input_tokens": 999999, "output_tokens": 999999}}
    stored["deepeval_cost_usd"] = 999.0
    stored["abstention_counts"] = {"abstained": 999, "answered": 0, "disagreement": 0, "unverified": 999,
                                   "run_failed": 0}
    stored["faithfulness_relevancy"] = {"overall": {"faithfulness": {"mean": 0.001, "n": 999},
                                                     "relevancy": {"mean": 0.001, "n": 999}},
                                        "by_category": {}, "no_retrieval": 999, "run_failed": 999}
    _write_fixtures(tmp_path, monkeypatch, stored=stored)

    result = rg.run_report_only()

    assert result["faithfulness_relevancy"]["overall"]["faithfulness"]["n"] == 1
    assert result["faithfulness_relevancy"]["overall"]["faithfulness"]["mean"] == 0.9
    assert result["abstention_counts"] == {"abstained": 0, "answered": 1, "disagreement": 0, "unverified": 0,
                                           "run_failed": 1}
    assert result["usage_by_model"]["gpt-4o"] == {"input_tokens": 30, "output_tokens": 8}
    assert result["extra_costs"]["gpt-4.1-mini"] == pytest.approx(0.002)

    report_text = (tmp_path / "generation.md").read_text(encoding="utf-8")
    assert "999999" not in report_text
    assert "999.0000" not in report_text
    assert "999" not in report_text.split("## Setup")[1].split("## Tool use")[0].replace("999999", "")


# --- Fix round 2: score_and_write_only, atomic writes and the answer_sha256 tripwire --------------

def test_score_and_write_only_leaves_both_files_untouched_when_golden_scoring_raises(tmp_path, monkeypatch):
    answers_path, scores_path, _ = _write_fixtures(tmp_path, monkeypatch)
    answers_before, scores_before = answers_path.read_bytes(), scores_path.read_bytes()
    all_rows = _fixture_answers()
    new_rows = [{"id": "g-01", "question": "q1", "category": "conceito", "answer": "nova resposta",
                "run_failed": False, "usage": {"input_tokens": 12, "output_tokens": 6},
                "tool_calls": ["search_knowledge_base"], "searched": True, "datajud_called": False,
                "contexts": ["ctx"]}]

    def raising_score_fn(rows, model):
        raise RuntimeError("deepeval boom")

    with pytest.raises(RuntimeError):
        rg.score_and_write_only(all_rows, new_rows, score_golden_fn=raising_score_fn)

    assert answers_path.read_bytes() == answers_before
    assert scores_path.read_bytes() == scores_before
    assert not list(tmp_path.glob("*.tmp*"))


def test_score_and_write_only_leaves_both_files_untouched_when_abstention_scoring_raises(tmp_path, monkeypatch):
    answers_path, scores_path, _ = _write_fixtures(tmp_path, monkeypatch)
    answers_before, scores_before = answers_path.read_bytes(), scores_path.read_bytes()
    all_rows = _fixture_answers()
    new_rows = [{"id": "oos-01", "question": "qo1", "category": "fora_de_escopo", "answer": "nova resposta",
                "run_failed": False, "usage": {"input_tokens": 12, "output_tokens": 6},
                "tool_calls": ["search_knowledge_base"], "searched": True, "datajud_called": False,
                "contexts": ["ctx"]}]

    def raising_abstain_fn(rows, clients):
        raise RuntimeError("judge boom")

    with pytest.raises(RuntimeError):
        rg.score_and_write_only(all_rows, new_rows, abstain_fn=raising_abstain_fn)

    assert answers_path.read_bytes() == answers_before
    assert scores_path.read_bytes() == scores_before


def test_score_and_write_only_writes_answer_sha256_into_scores_json(tmp_path, monkeypatch):
    from evals.groundtruth.generation.answers import answer_sha256
    answers_path, scores_path, _ = _write_fixtures(tmp_path, monkeypatch)
    all_rows = _fixture_answers()
    new_row = {"id": "oos-01", "question": "qo1", "category": "fora_de_escopo", "answer": "Não encontrei base.",
              "run_failed": False, "usage": {"input_tokens": 9, "output_tokens": 4},
              "tool_calls": ["search_knowledge_base"], "searched": True, "datajud_called": False,
              "contexts": ["ctx"]}

    def fake_abstain(rows, clients):
        return [{"id": "oos-01", "question": "qo1", "judges": {}, "label": "abstained",
                "answer_sha256": answer_sha256(rows[0]["answer"])}]

    merged = rg.score_and_write_only(all_rows, [new_row], abstain_fn=fake_abstain)

    saved = json.loads(scores_path.read_text(encoding="utf-8"))
    oos01 = [a for a in saved["abstention"] if a["id"] == "oos-01"][0]
    assert oos01["answer_sha256"] == answer_sha256("Não encontrei base.")
    assert merged == saved


def test_score_and_write_only_then_report_only_reflects_the_new_answer_and_cost(tmp_path, monkeypatch):
    """Fix round 2 ruling 1's mandated test: a merge that replaces rows changes the rendered cost and
    counts accordingly."""
    from evals.groundtruth.generation.answers import answer_sha256
    _write_fixtures(tmp_path, monkeypatch)
    before = rg.run_report_only()
    assert before["abstention_counts"]["run_failed"] == 1
    # oos-01 (failed) still contributes its stored judge usage (5,2) alongside oos-02's (5,2): 10,4 total.
    assert before["usage_by_model"]["gpt-4.1"] == {"input_tokens": 10, "output_tokens": 4}

    all_rows = _fixture_answers()
    new_answer = "Não encontrei base nos documentos."
    new_row = {"id": "oos-01", "question": "qo1", "category": "fora_de_escopo", "answer": new_answer,
              "run_failed": False, "status": "COMPLETED", "usage": {"input_tokens": 50, "output_tokens": 12},
              "tool_calls": ["search_knowledge_base"], "searched": True, "datajud_called": False,
              "contexts": ["ctx"]}

    def fake_abstain(rows, clients):
        return [{"id": "oos-01", "question": "qo1",
                "judges": {"gpt-4.1": {"verdict": {"abstained": "yes"}, "error": None,
                          "usage": {"input_tokens": 7, "output_tokens": 3}},
                          "claude-haiku-4-5": {"verdict": {"abstained": "yes"}, "error": None,
                          "usage": {"input_tokens": 7, "output_tokens": 3}}},
                "label": "abstained", "answer_sha256": answer_sha256(new_answer)}]

    rg.score_and_write_only(all_rows, [new_row], abstain_fn=fake_abstain)

    after = rg.run_report_only()
    assert after["abstention_counts"] == {"abstained": 1, "answered": 1, "disagreement": 0, "unverified": 0,
                                          "run_failed": 0}
    assert after["usage_by_model"]["gpt-4o"] == {"input_tokens": 80, "output_tokens": 20}  # +50/+12 from oos-01
    # oos-01's new judge usage (7,3) plus its carried-forward prior spend (5,2) plus oos-02's (5,2): 17,7.
    assert after["usage_by_model"]["gpt-4.1"] == {"input_tokens": 17, "output_tokens": 7}
    # The old (failed) attempt's spend was carried forward, not dropped, when its score item was replaced.
    assert before["usage_by_model"]["gpt-4.1"]["input_tokens"] < after["usage_by_model"]["gpt-4.1"]["input_tokens"]


def test_run_report_only_raises_on_a_stale_scores_json_left_by_a_partial_only_rerun(tmp_path, monkeypatch):
    """Fix round 2 ruling 2b: if answers.jsonl were somehow updated without a matching scores.json
    update (the exact partial-failure shape ruling 2a's write ordering defends against), run_report_only
    must raise naming the id instead of silently rendering the mismatched pair."""
    from evals.groundtruth.generation.answers import answer_sha256
    answers_path, scores_path, _ = _write_fixtures(tmp_path, monkeypatch)

    updated = _fixture_answers()
    updated[2] = {**updated[2], "answer": "uma resposta completamente diferente"}  # oos-02, answer changed
    with answers_path.open("w", encoding="utf-8") as f:
        for row in updated:
            f.write(json.dumps(row) + "\n")

    stored = _fixture_stored()
    stored["abstention"][1]["answer_sha256"] = answer_sha256("a2")  # still hashes the OLD answer text
    scores_path.write_text(json.dumps(stored), encoding="utf-8")

    with pytest.raises(ValueError):
        rg.run_report_only()
