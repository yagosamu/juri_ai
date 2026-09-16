"""Sampling of golden and out-of-scope questions for the generation run (Task 9b, brief R4).

select_questions is pure and deterministic: a fixed seed always draws the same golden subset, in
the order random.Random(seed).sample returns it, followed by every out-of-scope item in the order
it was given (file order, never resampled).
"""
import random
from typing import Any


def _as_item(obj: Any, kind: str) -> dict:
    """Normalize a GoldenItem (attribute access) or a plain dict (out-of-scope row) into one shape."""
    if isinstance(obj, dict):
        return {"id": obj["id"], "question": obj["question"], "category": obj["category"], "kind": kind}
    return {"id": obj.id, "question": obj.question, "category": obj.category, "kind": kind}


def select_questions(golden: list, out_of_scope: list, sample_size: int, seed: int) -> list[dict]:
    """sample_size golden items via random.Random(seed).sample, then every out_of_scope item in order."""
    sample = random.Random(seed).sample(list(golden), sample_size)
    return [_as_item(item, "golden") for item in sample] + [_as_item(item, "out_of_scope") for item in out_of_scope]
