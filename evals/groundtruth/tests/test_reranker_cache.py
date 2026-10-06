"""The harness reranker: one cross-encoder load per model instead of one per search, and a failure
that stops the run instead of quietly reporting vector-search numbers as rerank numbers.

Every test here injects a fake cross-encoder. The real BAAI/bge-reranker-v2-m3 is 2 GB and nothing
in this file may load it or reach the network.
"""
import numpy as np
import pytest
from agno.knowledge.document import Document

# CI installs evals/groundtruth/requirements.txt, which does not carry sentence-transformers: it is
# in requirements-local.txt, because only the rerank config needs it and it pulls in torch. Skipping
# the module keeps the gate green there; these tests run locally, where the harness reranker runs.
pytest.importorskip("sentence_transformers", reason="sentence-transformers is a local-only dependency")

import agno.knowledge.reranker.sentence_transformer as agno_reranker_mod  # noqa: E402
import sentence_transformers  # noqa: E402
from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker  # noqa: E402

from evals.groundtruth import reranker as reranker_mod  # noqa: E402
from evals.groundtruth.retriever import make_reranker  # noqa: E402

MODEL = "BAAI/bge-reranker-v2-m3"
OTHER_MODEL = "BAAI/bge-reranker-base"
QUERY = "qual o prazo do recurso?"
# Deliberately not in relevance order, so a reranker that returns the input list unchanged fails.
SCORES = {"o juiz decide em audiencia": 0.11, "o prazo para recurso e de quinze dias": 0.93,
          "dados do consumidor no contrato": 0.47}


class FakeCrossEncoder:
    """Stands in for sentence-transformers' CrossEncoder. Scores come from SCORES, not from a model."""

    def __init__(self, model_name_or_path=None, model_kwargs=None, local_files_only=False):
        self.model_name_or_path = model_name_or_path
        self.model_kwargs = model_kwargs
        self.local_files_only = local_files_only
        self.predict_calls = 0

    def predict(self, sentence_pairs):
        self.predict_calls += 1
        # agno calls .tolist() on whatever predict returns, so the fake returns an array too.
        return np.array([SCORES[content] for _query, content in sentence_pairs])


class ExplodingCrossEncoder(FakeCrossEncoder):
    def predict(self, sentence_pairs):
        raise RuntimeError("cross-encoder exploded")


def documents():
    """Fresh Documents every call: agno's reranker writes reranking_score onto the ones it is given."""
    return [Document(id=content, name=content, content=content) for content in SCORES]


@pytest.fixture
def builds(monkeypatch):
    """Record every cross-encoder the cache builds, and leave the cache empty either way."""
    made = []

    def build(model, model_kwargs=None):
        made.append(FakeCrossEncoder(model_name_or_path=model, model_kwargs=model_kwargs))
        return made[-1]

    reranker_mod.clear_cross_encoder_cache()
    monkeypatch.setattr(reranker_mod, "build_cross_encoder", build)
    yield made
    reranker_mod.clear_cross_encoder_cache()


def test_ten_searches_load_the_cross_encoder_once(builds):
    reranker = reranker_mod.CachedSentenceTransformerReranker(model=MODEL)
    for _ in range(10):
        reranker.rerank(QUERY, documents())
    assert len(builds) == 1
    assert builds[0].predict_calls == 10


def test_a_second_reranker_object_reuses_the_same_cross_encoder(builds):
    """The cache is module level because agno's Reranker is a pydantic model rebuilt per retriever."""
    reranker_mod.CachedSentenceTransformerReranker(model=MODEL).rerank(QUERY, documents())
    reranker_mod.CachedSentenceTransformerReranker(model=MODEL).rerank(QUERY, documents())
    assert len(builds) == 1


def test_clearing_the_cache_loads_the_cross_encoder_again(builds):
    reranker = reranker_mod.CachedSentenceTransformerReranker(model=MODEL)
    reranker.rerank(QUERY, documents())
    assert len(builds) == 1
    reranker_mod.clear_cross_encoder_cache()
    assert reranker_mod.cached_cross_encoder_models() == []
    reranker.rerank(QUERY, documents())
    assert len(builds) == 2
    assert builds[0] is not builds[1]


def test_two_model_names_get_two_instances(builds):
    first = reranker_mod.CachedSentenceTransformerReranker(model=MODEL)
    second = reranker_mod.CachedSentenceTransformerReranker(model=OTHER_MODEL)
    first.rerank(QUERY, documents())
    second.rerank(QUERY, documents())
    first.rerank(QUERY, documents())
    assert [encoder.model_name_or_path for encoder in builds] == [MODEL, OTHER_MODEL]
    assert reranker_mod.cached_cross_encoder_models() == sorted([MODEL, OTHER_MODEL])


def test_two_model_kwargs_for_one_model_get_two_instances(builds):
    """The key is the model and its kwargs: the same name at a different dtype is a different model."""
    reranker_mod.CachedSentenceTransformerReranker(
        model=MODEL, model_kwargs={"torch_dtype": "float32"}).rerank(QUERY, documents())
    reranker_mod.CachedSentenceTransformerReranker(
        model=MODEL, model_kwargs={"torch_dtype": "float16"}).rerank(QUERY, documents())
    reranker_mod.CachedSentenceTransformerReranker(
        model=MODEL, model_kwargs={"torch_dtype": "float32"}).rerank(QUERY, documents())
    assert len(builds) == 2
    assert [encoder.model_kwargs for encoder in builds] == [{"torch_dtype": "float32"},
                                                            {"torch_dtype": "float16"}]


def test_empty_documents_return_empty_without_loading_anything(builds):
    assert reranker_mod.CachedSentenceTransformerReranker(model=MODEL).rerank(QUERY, []) == []
    assert builds == []


@pytest.mark.parametrize("top_n", [None, 2])
def test_documents_order_and_scores_are_identical_to_agno(builds, monkeypatch, top_n):
    """This task changes when the model is loaded, nothing about how documents are scored."""
    monkeypatch.setattr(agno_reranker_mod, "CrossEncoder", FakeCrossEncoder)
    library = SentenceTransformerReranker(model=MODEL, top_n=top_n).rerank(QUERY, documents())
    harness = reranker_mod.CachedSentenceTransformerReranker(
        model=MODEL, top_n=top_n).rerank(QUERY, documents())
    assert [doc.content for doc in harness] == [doc.content for doc in library]
    assert [doc.reranking_score for doc in harness] == [doc.reranking_score for doc in library]
    assert [doc.content for doc in harness][0] == "o prazo para recurso e de quinze dias"
    assert len(harness) == (3 if top_n is None else 2)


def test_agno_swallows_a_failing_cross_encoder(monkeypatch):
    """Pins the library behaviour the harness deliberately departs from in the next test."""
    monkeypatch.setattr(agno_reranker_mod, "CrossEncoder", ExplodingCrossEncoder)
    docs = documents()
    returned = SentenceTransformerReranker(model=MODEL).rerank(QUERY, docs)
    assert returned is docs
    assert all(doc.reranking_score is None for doc in returned)


def test_the_harness_raises_instead_of_returning_the_documents_unreranked(monkeypatch):
    reranker_mod.clear_cross_encoder_cache()
    monkeypatch.setattr(reranker_mod, "build_cross_encoder",
                        lambda model, model_kwargs=None: ExplodingCrossEncoder())
    with pytest.raises(RuntimeError, match="cross-encoder exploded"):
        reranker_mod.CachedSentenceTransformerReranker(model=MODEL).rerank(QUERY, documents())
    reranker_mod.clear_cross_encoder_cache()


def test_the_cross_encoder_is_built_from_the_local_cache_only(monkeypatch):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return FakeCrossEncoder(**kwargs)

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", fake)
    reranker_mod.build_cross_encoder(MODEL, {"torch_dtype": "float32"})
    assert seen["model_name_or_path"] == MODEL
    assert seen["model_kwargs"] == {"torch_dtype": "float32"}
    assert seen["local_files_only"] is True


def test_a_model_missing_from_the_local_cache_names_it_and_says_to_fetch_it(monkeypatch):
    def fake(**kwargs):
        raise OSError("we couldn't connect to huggingface.co")

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", fake)
    with pytest.raises(RuntimeError) as excinfo:
        reranker_mod.build_cross_encoder(MODEL)
    message = str(excinfo.value)
    assert MODEL in message
    assert "Hugging Face" in message
    assert "outside" in message


def test_make_reranker_returns_the_caching_subclass():
    reranker = make_reranker("bge-reranker-v2-m3")
    assert isinstance(reranker, reranker_mod.CachedSentenceTransformerReranker)
    assert reranker.model == MODEL


def test_make_reranker_keeps_none_and_its_error_for_an_unknown_name():
    assert make_reranker(None) is None
    with pytest.raises(ValueError) as excinfo:
        make_reranker("nao-existe")
    assert "nao-existe" in str(excinfo.value)
