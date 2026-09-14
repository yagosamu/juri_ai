import hashlib
import json
from dataclasses import replace

import pytest
from agno.knowledge.embedder.base import Embedder

from evals.groundtruth.config import RetrievalConfig
from evals.groundtruth.indexer import build_index, index_fingerprint
from evals.groundtruth.retriever import IndexMismatch, LanceDbRetriever, chunk_offsets


class BagEmbedder(Embedder):
    """Deterministic embedding: counts of 8 keyword buckets, so tests can predict neighbours."""

    words = ["prazo", "recurso", "contrato", "dados", "consumidor", "empregado", "juiz", "multa"]

    def __init__(self):
        self.dimensions = len(self.words)

    def get_embedding(self, text):
        low = text.lower()
        return [float(low.count(w)) + 1e-3 for w in self.words]

    def get_embedding_and_usage(self, text):
        return self.get_embedding(text), None


CORPUS = {
    "a": "Art. 1º O prazo para recurso é de quinze dias. " * 6 + "Art. 2º O juiz decide. " * 6,
    "b": "Art. 1º O consumidor tem direito a dados claros sobre o contrato. " * 8,
}


def test_chunk_offsets_reproduce_agno_chunking():
    offsets = chunk_offsets(CORPUS["a"], chunk_size=120, overlap=20)
    assert offsets[1][0] == 0
    assert len(offsets) >= 3
    for start, end in offsets.values():
        assert 0 <= start < end <= len(CORPUS["a"])
    assert offsets[2][0] < offsets[1][1]


def test_build_index_then_search_returns_spans_in_corpus(tmp_path):
    cfg = RetrievalConfig("t", chunk_size=120, chunk_overlap=20, search_type="vector", reranker=None,
                          embedder_id="bag", embedder_dimensions=8, max_results=3)
    emb = BagEmbedder()
    build_index(cfg, CORPUS, emb, indexes_dir=tmp_path)
    assert index_fingerprint(cfg, tmp_path) == cfg.fingerprint()
    retriever = LanceDbRetriever(cfg, CORPUS, emb, indexes_dir=tmp_path)
    hits = retriever.search("qual o prazo do recurso?", k=3)
    assert len(hits) == 3
    assert hits[0].doc_id == "a"
    assert CORPUS[hits[0].doc_id][hits[0].start:hits[0].end] == hits[0].text


def _build(tmp_path, corpus=None, **overrides):
    cfg = RetrievalConfig("t", chunk_size=120, chunk_overlap=20, search_type="vector", reranker=None,
                          embedder_id="bag", embedder_dimensions=8, max_results=3)
    cfg = replace(cfg, **overrides) if overrides else cfg
    build_index(cfg, corpus or CORPUS, BagEmbedder(), indexes_dir=tmp_path)
    return cfg


def test_index_name_includes_embedder_dimensions():
    """Two configs sharing a model id but not its dimension must not share a table."""
    base = RetrievalConfig("t", 120, 20, "vector", None, embedder_id="bag", embedder_dimensions=8)
    reduced = replace(base, embedder_dimensions=4)
    assert base.index_name != reduced.index_name
    assert "d8" in base.index_name and "d4" in reduced.index_name


def test_fingerprint_file_records_corpus_hashes(tmp_path):
    cfg = _build(tmp_path)
    manifest = json.loads((tmp_path / f"{cfg.index_name}.json").read_text(encoding="utf-8"))
    assert manifest["corpus_sha256"] == {
        doc_id: hashlib.sha256(text.encode("utf-8")).hexdigest() for doc_id, text in CORPUS.items()
    }


def test_retriever_refuses_a_corpus_the_index_was_not_built_from(tmp_path):
    cfg = _build(tmp_path)
    altered = dict(CORPUS, a=CORPUS["a"] + " Art. 3 Novo texto acrescentado. ")
    with pytest.raises(IndexMismatch) as excinfo:
        LanceDbRetriever(cfg, altered, BagEmbedder(), indexes_dir=tmp_path)
    message = str(excinfo.value)
    assert "'a'" in message
    assert "evals.groundtruth.indexer" in message


def test_retriever_refuses_a_corpus_with_an_unknown_document(tmp_path):
    cfg = _build(tmp_path)
    altered = dict(CORPUS, c="Art. 1 Documento que o indice nao conhece. " * 4)
    with pytest.raises(IndexMismatch) as excinfo:
        LanceDbRetriever(cfg, altered, BagEmbedder(), indexes_dir=tmp_path)
    assert "'c'" in str(excinfo.value)


def test_retriever_refuses_a_corpus_missing_an_indexed_document(tmp_path):
    cfg = _build(tmp_path)
    with pytest.raises(IndexMismatch) as excinfo:
        LanceDbRetriever(cfg, {"a": CORPUS["a"]}, BagEmbedder(), indexes_dir=tmp_path)
    assert "'b'" in str(excinfo.value)


def test_retriever_refuses_a_config_whose_chunking_differs(tmp_path):
    cfg = _build(tmp_path)
    # Same index name, different chunking: rewrite the fingerprint as a stale build would leave it.
    path = tmp_path / f"{cfg.index_name}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["fingerprint"]["chunk_size"] = 999
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(IndexMismatch) as excinfo:
        LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)
    message = str(excinfo.value)
    assert "chunk_size" in message and "999" in message and "120" in message


def test_retriever_refuses_a_missing_fingerprint(tmp_path):
    cfg = _build(tmp_path)
    (tmp_path / f"{cfg.index_name}.json").unlink()
    with pytest.raises(IndexMismatch) as excinfo:
        LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)
    assert "evals.groundtruth.indexer" in str(excinfo.value)


def test_unknown_chunk_in_a_result_raises_an_informative_error(tmp_path):
    cfg = _build(tmp_path)
    retriever = LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)

    class Ghost:
        meta_data = {"name": "a", "chunk": 9999}

    retriever.vector_db.search = lambda *a, **kw: [Ghost()]
    with pytest.raises(ValueError) as excinfo:
        retriever.search("qualquer coisa", k=1)
    message = str(excinfo.value)
    assert "9999" in message and "'a'" in message and cfg.name in message and cfg.index_name in message


def test_unknown_document_in_a_result_raises_an_informative_error(tmp_path):
    cfg = _build(tmp_path)
    retriever = LanceDbRetriever(cfg, CORPUS, BagEmbedder(), indexes_dir=tmp_path)

    class Ghost:
        meta_data = {"name": "zzz", "chunk": 1}

    retriever.vector_db.search = lambda *a, **kw: [Ghost()]
    with pytest.raises(ValueError) as excinfo:
        retriever.search("qualquer coisa", k=1)
    message = str(excinfo.value)
    assert "'zzz'" in message and cfg.name in message and cfg.index_name in message
