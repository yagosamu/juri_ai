import pytest

from evals.groundtruth.generation.cost import model_cost, scale_usage, total_cost


def test_model_cost_computes_input_and_output_separately():
    cost = model_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(2.50 + 10.0)


def test_model_cost_embedding_model_has_no_output_price():
    cost = model_cost("text-embedding-3-small", input_tokens=1_000_000, output_tokens=0)
    assert cost == pytest.approx(0.02)


def test_total_cost_sums_across_models():
    usage = {"gpt-4o": {"input_tokens": 1_000_000, "output_tokens": 0},
             "gpt-4.1-mini": {"input_tokens": 1_000_000, "output_tokens": 0}}
    assert total_cost(usage) == pytest.approx(2.50 + 0.40)


def test_scale_usage_multiplies_both_token_counts():
    scaled = scale_usage({"input_tokens": 100, "output_tokens": 50}, factor=5)
    assert scaled == {"input_tokens": 500, "output_tokens": 250}


def test_model_cost_unknown_model_raises_key_error():
    with pytest.raises(KeyError):
        model_cost("nonexistent-model", 1, 1)
