import random
from types import SimpleNamespace

from evals.groundtruth.generation.select import select_questions


def _golden(n):
    return [SimpleNamespace(id=f"g-{i:02d}", question=f"question {i}", category="conceito") for i in range(n)]


def _oos(n):
    return [{"id": f"oos-{i:02d}", "question": f"oos question {i}", "category": "fora_de_escopo"} for i in range(n)]


def test_select_questions_returns_sample_size_golden_plus_all_out_of_scope():
    golden, oos = _golden(8), _oos(3)
    selected = select_questions(golden, oos, sample_size=4, seed=7)
    assert len(selected) == 7
    assert [s["kind"] for s in selected] == ["golden"] * 4 + ["out_of_scope"] * 3


def test_select_questions_is_deterministic_for_a_given_seed():
    golden, oos = _golden(10), _oos(2)
    first = select_questions(golden, oos, sample_size=5, seed=7)
    second = select_questions(golden, oos, sample_size=5, seed=7)
    assert [s["id"] for s in first] == [s["id"] for s in second]


def test_select_questions_matches_random_sample_order():
    golden, oos = _golden(10), _oos(1)
    selected = select_questions(golden, oos, sample_size=5, seed=7)
    expected_ids = [g.id for g in random.Random(7).sample(golden, 5)]
    assert [s["id"] for s in selected[:5]] == expected_ids


def test_select_questions_keeps_out_of_scope_file_order():
    golden, oos = _golden(5), _oos(4)
    selected = select_questions(golden, oos, sample_size=2, seed=1)
    assert [s["id"] for s in selected[2:]] == [o["id"] for o in oos]


def test_select_questions_does_not_mutate_inputs():
    golden, oos = _golden(6), _oos(2)
    golden_ids_before = [g.id for g in golden]
    select_questions(golden, oos, sample_size=3, seed=7)
    assert [g.id for g in golden] == golden_ids_before


def test_select_questions_normalizes_golden_items_to_dicts_with_kind():
    golden, oos = _golden(3), _oos(1)
    selected = select_questions(golden, oos, sample_size=2, seed=7)
    for item in selected:
        assert set(item) == {"id", "question", "category", "kind"}
