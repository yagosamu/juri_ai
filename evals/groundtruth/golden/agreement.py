"""Inter-rater agreement between two label lists: percent agreement and Cohen's kappa, used to compare the
two golden-set judges."""
from collections import Counter


def _check(a: list, b: list) -> None:
    if not a or len(a) != len(b):
        raise ValueError("label lists must be non-empty and of equal length")


def percent_agreement(a: list, b: list) -> float:
    _check(a, b)
    return sum(x == y for x, y in zip(a, b)) / len(a)


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa; None when expected agreement is 1, where kappa is undefined."""
    _check(a, b)
    n = len(a)
    observed = percent_agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if expected == 1.0:
        return None
    return (observed - expected) / (1 - expected)
