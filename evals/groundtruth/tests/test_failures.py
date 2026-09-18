"""Tests for evals/groundtruth/failures.py (Task 15, brief 2026-09-13/task-15-brief.md): deterministic
evidence for the questions production misses at recall@10."""
import pytest

from evals.groundtruth import failures as failures_mod
from evals.groundtruth.config import CANDIDATES, GOLDEN_SET, RESULTS_DIR
from evals.groundtruth.failures import (build_failure_rows, build_failures_report, first_hit_rank,
                                        load_candidates, passage_info, production_misses,
                                        render_failures)
from evals.groundtruth.golden.schema import load_golden
from evals.groundtruth.scorers import Span


# ---------------------------------------------------------------------------
# production_misses
# ---------------------------------------------------------------------------

def test_production_misses_returns_ids_with_recall_at_10_zero():
    production_result = {"items": [
        {"id": "a", "recall@10": 0.0},
        {"id": "b", "recall@10": 1.0},
        {"id": "c", "recall@10": 0.0},
    ]}

    assert production_misses(production_result) == ["a", "c"]


def test_production_misses_preserves_items_order():
    production_result = {"items": [
        {"id": "z", "recall@10": 0.0},
        {"id": "a", "recall@10": 0.0},
    ]}

    assert production_misses(production_result) == ["z", "a"]


# ---------------------------------------------------------------------------
# passage_info
# ---------------------------------------------------------------------------

def test_passage_info_reports_doc_id_header_and_length():
    golden_item = {"id": "r1-x-1", "passages": [{"doc_id": "cpc", "start": 100, "end": 250}]}
    candidates_by_id = {"r1-x-1": {"header": "Art. 42"}}

    info = passage_info(golden_item, candidates_by_id)

    assert info == {"doc_id": "cpc", "header": "Art. 42", "length": 150}


def test_passage_info_uses_unknown_header_when_candidate_missing():
    golden_item = {"id": "r1-x-2", "passages": [{"doc_id": "clt", "start": 0, "end": 10}]}

    info = passage_info(golden_item, {})

    assert info["header"] == "unknown"
    assert info["doc_id"] == "clt"
    assert info["length"] == 10


# ---------------------------------------------------------------------------
# first_hit_rank
# ---------------------------------------------------------------------------

def test_first_hit_rank_finds_the_rank_of_the_first_overlapping_chunk():
    passage = Span("cpc", 100, 200)
    retrieved = [["cpc", 0, 50], ["cpc", 150, 250], ["cpc", 100, 200]]

    assert first_hit_rank(retrieved, passage) == 2


def test_first_hit_rank_is_one_indexed():
    passage = Span("cpc", 100, 200)
    retrieved = [["cpc", 100, 200]]

    assert first_hit_rank(retrieved, passage) == 1


def test_first_hit_rank_returns_none_when_nothing_overlaps():
    passage = Span("cpc", 100, 200)
    retrieved = [["cpc", 0, 50], ["clt", 100, 200]]

    assert first_hit_rank(retrieved, passage) is None


# ---------------------------------------------------------------------------
# build_failure_rows
# ---------------------------------------------------------------------------

def test_build_failure_rows_assembles_one_row_per_miss_with_every_config_rank():
    golden_by_id = {
        "r1-x-1": {"id": "r1-x-1", "category": "conceito", "question": "Q1?",
                   "passages": [{"doc_id": "cpc", "start": 0, "end": 100}]},
    }
    candidates_by_id = {"r1-x-1": {"header": "Art. 1"}}
    results_by_config = {
        "production": {"items": [{"id": "r1-x-1", "recall@10": 0.0, "retrieved": [["cpc", 500, 600]]}]},
        "chunk1500": {"items": [{"id": "r1-x-1", "recall@10": 1.0, "retrieved": [["cpc", 0, 100]]}]},
    }

    rows = build_failure_rows(["r1-x-1"], golden_by_id, candidates_by_id, results_by_config,
                               config_order=["production", "chunk1500"])

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == "r1-x-1"
    assert row["category"] == "conceito"
    assert row["question"] == "Q1?"
    assert row["doc_id"] == "cpc"
    assert row["header"] == "Art. 1"
    assert row["length"] == 100
    assert row["ranks"] == {"production": None, "chunk1500": 1}


# ---------------------------------------------------------------------------
# render_failures
# ---------------------------------------------------------------------------

def _one_row():
    return [{"id": "r1-x-1", "category": "conceito", "question": "Q1?", "doc_id": "cpc",
             "header": "Art. 1", "length": 100,
             "ranks": {"production": None, "chunk1500": 1, "chunk800": 1, "hybrid": 1, "rerank": 1}}]


def test_render_failures_lists_the_question_id_and_category():
    text = render_failures(_one_row(), config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    assert "r1-x-1" in text
    assert "conceito" in text
    assert "Q1?" in text


def test_render_failures_shows_miss_and_rank_per_config():
    text = render_failures(_one_row(), config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    assert "miss" in text
    assert "1" in text


def test_render_failures_states_when_there_are_no_misses():
    text = render_failures([], config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    assert "0" in text


def test_render_failures_table_separator_matches_header_column_count():
    text = render_failures(_one_row(), config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    header_line = next(line for line in text.splitlines() if line.startswith("| id |"))
    sep_line = next(line for line in text.splitlines() if line.startswith("|---"))
    header_cols = header_line.count("|") - 1
    sep_cols = sep_line.count("|") - 1
    assert header_cols == sep_cols


def test_render_failures_has_no_em_dash_or_en_dash():
    text = render_failures(_one_row(), config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    assert "—" not in text
    assert "–" not in text


def test_render_failures_does_not_cite_the_gitignored_brief_path():
    # Fix round 1, Important 2: .superpowers/ is gitignored, so a reader of the committed report
    # cannot open that path. The report must point only at committed artifacts.
    text = render_failures(_one_row(), config_order=["production", "chunk1500", "chunk800", "hybrid", "rerank"])

    assert ".superpowers" not in text
    assert "task-15-brief" not in text


# ---------------------------------------------------------------------------
# Fix round 1, Important 5: an end-to-end test binds the real inputs to the committed
# results/failures.md. results/*.json is gitignored, so this test must skip cleanly (never fail)
# when those files are absent, e.g. on a fresh CI checkout.
# ---------------------------------------------------------------------------

def test_build_failures_report_matches_the_committed_report_byte_for_byte():
    missing = [name for name in failures_mod.CONFIG_ORDER
               if not (RESULTS_DIR / f"{name}.json").exists()]
    if missing or not GOLDEN_SET.exists() or not CANDIDATES.exists():
        pytest.skip(f"results/*.json not present (gitignored): missing {missing}")

    results_by_config = {name: failures_mod._load_json(RESULTS_DIR / f"{name}.json")
                          for name in failures_mod.CONFIG_ORDER}
    golden = load_golden(GOLDEN_SET)
    candidates_by_id = load_candidates()

    actual = build_failures_report(results_by_config, golden, candidates_by_id)
    committed = (RESULTS_DIR / "failures.md").read_text(encoding="utf-8")

    assert actual == committed
