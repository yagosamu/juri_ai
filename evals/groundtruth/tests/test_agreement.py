import math

import pytest

from evals.groundtruth.golden.agreement import cohen_kappa, percent_agreement


def test_percent_agreement():
    assert percent_agreement(["a", "b", "a"], ["a", "b", "b"]) == 2 / 3


def test_kappa_perfect_agreement_is_one():
    assert cohen_kappa(["y", "n", "y", "n"], ["y", "n", "y", "n"]) == 1.0


def test_kappa_known_value():
    a = ["y"] * 20 + ["n"] * 30
    b = ["y"] * 15 + ["n"] * 5 + ["y"] * 10 + ["n"] * 20
    # observed 35/50 = 0.7; expected 0.4 * 0.5 + 0.6 * 0.5 = 0.5; kappa = 0.2 / 0.5 = 0.4
    assert math.isclose(cohen_kappa(a, b), 0.4)


def test_kappa_is_undefined_when_both_raters_use_one_class():
    assert cohen_kappa(["y", "y", "y"], ["y", "y", "y"]) is None


@pytest.mark.parametrize("a, b", [(["a"], ["a", "b"]), ([], [])])
def test_mismatched_or_empty_inputs_raise(a, b):
    with pytest.raises(ValueError):
        percent_agreement(a, b)
