"""The benchmark's cross-encoder reranker: agno's scoring, loaded once instead of once per search.

agno 2.4.7's `SentenceTransformerReranker._rerank` constructs a `CrossEncoder` inside every call
(`agno/knowledge/reranker/sentence_transformer.py:22`), so each search reads the 2 GB
BAAI/bge-reranker-v2-m3 from disk again. Over the 59 golden questions that is the whole of the
45356 ms p50 in `results/report.md`. This module keeps the loaded model in a module-level cache and
subclasses agno's reranker to read from it; the scoring, sorting and `top_n` behaviour below is
agno's, copied unchanged.

Lives beside `retriever.py` rather than inside it because importing agno's reranker imports
sentence-transformers and torch, about 7 seconds, and `retriever.py` is imported by every harness
entry point including the four configs that do not rerank. `retriever.make_reranker` imports this
module only when a config asks for a reranker.
"""
from typing import Any, Dict, List, Optional

from agno.knowledge.document import Document
from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker

# Loaded cross-encoders, keyed by model name and the kwargs it was built with: the same name at a
# different dtype or device is a different model. The cache is module level, not an attribute, so
# that it survives the reranker objects themselves, which agno rebuilds per retriever because
# `Reranker` is a pydantic model. Inspect it with `cached_cross_encoder_models`, empty it with
# `clear_cross_encoder_cache`.
_CROSS_ENCODER_CACHE: Dict[tuple, Any] = {}


def _cache_key(model: str, model_kwargs: Optional[Dict[str, Any]]) -> tuple:
    return model, tuple(sorted((key, repr(value)) for key, value in (model_kwargs or {}).items()))


def build_cross_encoder(model: str, model_kwargs: Optional[Dict[str, Any]] = None):
    """Load one cross-encoder from the local Hugging Face cache. Tests replace this with a fake.

    `local_files_only=True` is the point: a benchmark run must never spend its measured latency on a
    download, and a model that is not already on this machine must be a loud failure rather than a
    silent 2 GB fetch in the middle of a timed search.
    """
    import sentence_transformers

    try:
        return sentence_transformers.CrossEncoder(
            model_name_or_path=model, model_kwargs=model_kwargs, local_files_only=True)
    except OSError as exc:
        raise RuntimeError(
            f"Cross-encoder {model!r} is not in the local Hugging Face cache, and this harness will "
            f"not download it during a measured run. Fetch it once outside the benchmark, then run "
            f"again: python -c \"from sentence_transformers import CrossEncoder; "
            f"CrossEncoder({model!r})\"") from exc


def load_cross_encoder(model: str, model_kwargs: Optional[Dict[str, Any]] = None):
    """Return the cached cross-encoder for this model and kwargs, building it on first use."""
    key = _cache_key(model, model_kwargs)
    if key not in _CROSS_ENCODER_CACHE:
        _CROSS_ENCODER_CACHE[key] = build_cross_encoder(model, model_kwargs)
    return _CROSS_ENCODER_CACHE[key]


def cached_cross_encoder_models() -> List[str]:
    """The model names currently held in the cache, sorted; duplicated once per kwargs variant."""
    return sorted(model for model, _kwargs in _CROSS_ENCODER_CACHE)


def clear_cross_encoder_cache() -> None:
    """Drop every loaded cross-encoder, so the next rerank takes the cold path again."""
    _CROSS_ENCODER_CACHE.clear()


class CachedSentenceTransformerReranker(SentenceTransformerReranker):
    """agno's SentenceTransformerReranker with the model loaded once and errors left to propagate."""

    def _rerank(self, query: str, documents: List[Document]) -> List[Document]:
        # agno's _rerank, with its per-call `CrossEncoder(...)` replaced by the cached load. Scoring,
        # sorting and top_n are left exactly as the library does them.
        if not documents:
            return []

        sentence_transformer_client = load_cross_encoder(self.model, self.model_kwargs)

        top_n = self.top_n
        if top_n and not (0 < top_n):
            from agno.utils.log import logger

            logger.warning(f"top_n should be a positive integer, got {self.top_n}, setting top_n to None")
            top_n = None

        compressed_docs: list[Document] = []

        sentence_pairs = [[query, doc.content] for doc in documents]

        scores = sentence_transformer_client.predict(sentence_pairs).tolist()
        for index, score in enumerate(scores):
            doc = documents[index]
            doc.reranking_score = score
            compressed_docs.append(doc)

        compressed_docs.sort(
            key=lambda x: x.reranking_score if x.reranking_score is not None else float("-inf"),
            reverse=True,
        )

        if top_n:
            compressed_docs = compressed_docs[:top_n]

        return compressed_docs

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        # agno's Reranker.rerank catches every exception, logs it and returns the documents
        # unreranked (sentence_transformer.py:49-54). The harness chooses differently: a run that
        # silently fell back to plain vector search would report vector numbers in the `rerank` row
        # of results/report.md, and the project would publish them as reranker numbers. A crash is
        # recoverable; a published wrong number is not. Production is unaffected: ia/ sets
        # RERANKER = None and never reaches this class.
        return self._rerank(query=query, documents=documents)
