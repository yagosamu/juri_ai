"""Retriever interface for the benchmark. LanceDbRetriever calls the same agno LanceDb.search that
production's Knowledge.search calls, including the post-search cliente_id filter."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.document.base import Document
from agno.knowledge.embedder.base import Embedder
from agno.knowledge.reranker.base import Reranker
from agno.vectordb.distance import Distance
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType

from evals.groundtruth.config import INDEXES_DIR, RetrievalConfig
from evals.groundtruth.indexer import TENANT, corpus_sha256, read_fingerprint_file, rebuild_command

# agno 2.4.7's LanceDb.search asks LanceDB for `limit` rows and only then drops, in Python, the rows
# whose cliente_id does not match the filter (lance_db.py:474-503). On a table shared by many
# clients, a client whose chunks are a minority can get fewer than k rows, or none. Asking for 10
# times as many rows before the filter lowers that risk without a schema change; it does not remove
# it, so a shortfall is recorded on the retriever instead of hidden behind a retry loop. Measured in
# results/multitenant.md.
OVERFETCH_FACTOR = 10


@dataclass(frozen=True)
class RetrievedChunk:
    doc_id: str
    start: int
    end: int
    text: str


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[RetrievedChunk]: ...


def chunk_offsets(text: str, chunk_size: int, overlap: int) -> dict[int, tuple[int, int]]:
    """Re-run Agno's chunker on the normalized text and map chunk number -> (start, end)."""
    chunks = FixedSizeChunking(chunk_size=chunk_size, overlap=overlap).chunk(Document(content=text, name="x", id="x"))
    offsets, cursor = {}, 0
    for doc in chunks:
        start = text.find(doc.content, cursor)
        if start < 0:
            raise ValueError(f"chunk {doc.meta_data['chunk']} not found in text; corpus not normalized?")
        offsets[doc.meta_data["chunk"]] = (start, start + len(doc.content))
        cursor = start + 1
    return offsets


def make_reranker(name: Optional[str]) -> Optional[Reranker]:
    if name is None:
        return None
    if name == "bge-reranker-v2-m3":
        from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker

        return SentenceTransformerReranker(model="BAAI/bge-reranker-v2-m3")
    raise ValueError(f"unknown reranker {name}")


class IndexMismatch(RuntimeError):
    """The index on disk was not built from the config and corpus a retriever was handed."""


def check_index_matches(config: RetrievalConfig, corpus: dict[str, str], indexes_dir: Path) -> None:
    """Raise IndexMismatch unless the fingerprint file proves the table came from this config and corpus.

    Spans are computed by re-chunking the corpus handed in, so a table built from other text would map
    every search result onto the wrong characters without any error.
    """
    rebuild = f"Rebuild the index with: {rebuild_command(config)}"
    record = read_fingerprint_file(config, indexes_dir)
    if record is None:
        raise IndexMismatch(
            f"Index {config.index_name!r} in {indexes_dir} has no fingerprint file, so nothing proves which "
            f"config and corpus it was built from. {rebuild}")
    problems = []
    built = record.get("fingerprint") or {}
    for key, expected in config.fingerprint().items():
        if built.get(key) != expected:
            problems.append(f"{key} is {built.get(key)!r} in the index but {expected!r} in config {config.name!r}")
    built_hashes = record.get("corpus_sha256")
    if not isinstance(built_hashes, dict):
        problems.append("the fingerprint records no corpus_sha256, so the corpus it was built from is unknown")
    else:
        current = corpus_sha256(corpus)
        for doc_id in sorted(set(built_hashes) | set(current)):
            if doc_id not in current:
                problems.append(f"document {doc_id!r} is in the index but not in the corpus")
            elif doc_id not in built_hashes:
                problems.append(f"document {doc_id!r} is in the corpus but not in the index")
            elif built_hashes[doc_id] != current[doc_id]:
                problems.append(f"document {doc_id!r} has changed since the index was built")
    if problems:
        raise IndexMismatch(
            f"Index {config.index_name!r} in {indexes_dir} does not match what it was handed: "
            + "; ".join(problems) + f". {rebuild}")


class LanceDbRetriever:
    def __init__(self, config: RetrievalConfig, corpus: dict[str, str], embedder: Embedder,
                 indexes_dir: Path = INDEXES_DIR):
        check_index_matches(config, corpus, indexes_dir)  # before LanceDb opens the table
        self.name = config.name
        self.config = config
        self.offsets = {doc_id: chunk_offsets(text, config.chunk_size, config.chunk_overlap)
                        for doc_id, text in corpus.items()}
        self.corpus = corpus
        self.vector_db = LanceDb(uri=str(indexes_dir), table_name=config.index_name, embedder=embedder,
                                 search_type=SearchType(config.search_type), distance=Distance(config.distance),
                                 reranker=make_reranker(config.reranker), use_tantivy=False)
        self.overfetch_factor = OVERFETCH_FACTOR
        # The last search's shortfall report: rows asked of agno before the cliente_id filter, rows
        # that survived it, and how many of the k requested were missing (0 when k survived).
        self.last_requested_limit: Optional[int] = None
        self.last_survivors: Optional[int] = None
        self.last_shortfall: Optional[int] = None

    def search(self, query: str, k: int) -> list[RetrievedChunk]:
        # Over-fetch only where it cannot reorder the top k: plain vector search returns rows by
        # distance, so the first k survivors of k * factor rows are the rows a pre-filter would give.
        # agno reranks every row that survives the filter (lance_db.py:505-506), so the reranked path
        # keeps its candidate count; hybrid search fuses two ranked lists cut at `limit`, so a longer
        # cut changes the fused order (measured: all 59 golden top 10s changed, recall@10 0.966 to
        # 0.949). Both keep their single-tenant numbers in results/report.md.
        if self.config.reranker:
            limit = self.config.rerank_candidates
        elif self.config.search_type == SearchType.vector.value:
            limit = k * self.overfetch_factor
        else:
            limit = k
        docs = self.vector_db.search(query, limit=limit, filters={"cliente_id": TENANT})
        self.last_requested_limit = limit
        self.last_survivors = len(docs)
        self.last_shortfall = max(0, k - len(docs))
        out = []
        for doc in docs[:k]:
            # Both doc.name and meta_data["name"] carry the doc_id; the metadata entry is the one
            # this indexer writes itself, so it does not depend on how the reader names documents.
            doc_id, chunk = doc.meta_data.get("name"), doc.meta_data.get("chunk")
            if doc_id not in self.offsets:
                raise ValueError(
                    f"Search result names document {doc_id!r} chunk {chunk!r}, but config {self.config.name!r} "
                    f"has no such document in the corpus behind index {self.config.index_name!r}.")
            if chunk not in self.offsets[doc_id]:
                raise ValueError(
                    f"Search result names document {doc_id!r} chunk {chunk!r}, but config {self.config.name!r} "
                    f"splits that document into {len(self.offsets[doc_id])} chunks, so index "
                    f"{self.config.index_name!r} does not match the corpus.")
            start, end = self.offsets[doc_id][chunk]
            out.append(RetrievedChunk(doc_id, start, end, self.corpus[doc_id][start:end]))
        return out


def build_retriever(config: RetrievalConfig, corpus: dict[str, str], embedder: Embedder,
                    indexes_dir: Path = INDEXES_DIR) -> Retriever:
    return LanceDbRetriever(config, corpus, embedder, indexes_dir)
