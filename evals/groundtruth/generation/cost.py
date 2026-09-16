"""Prices recorded by the controller on 2026-09-15 (task-9b-brief.md R1 table), and pure cost math."""

PRICES_PER_MILLION_TOKENS = {
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}

PRICE_SOURCE = ("gpt-4o, gpt-4.1-mini and gpt-4.1: developers.openai.com model page. "
               "claude-haiku-4-5: platform.claude.com pricing page. "
               "text-embedding-3-small: fetched 2026-09-14. Recorded by the controller on 2026-09-15.")


def model_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICES_PER_MILLION_TOKENS[model]
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def total_cost(usage_by_model: dict) -> float:
    """usage_by_model: {model: {"input_tokens": x, "output_tokens": y}}."""
    return sum(model_cost(model, u["input_tokens"], u["output_tokens"]) for model, u in usage_by_model.items())


def scale_usage(usage: dict, factor: float) -> dict:
    """Linearly project measured smoke usage to a larger run size."""
    return {"input_tokens": usage["input_tokens"] * factor, "output_tokens": usage["output_tokens"] * factor}
