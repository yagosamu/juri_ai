"""Build a LanceDB index for one RetrievalConfig using the same Agno path production uses
(Knowledge.insert -> TextReader -> FixedSizeChunking -> LanceDb.insert).
Usage: .venv/Scripts/python.exe -m evals.groundtruth.indexer --config production [--offline]"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.embedder.base import Embedder
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.text_reader import TextReader
from agno.vectordb.distance import Distance
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType

from evals.groundtruth.config import CACHE_DIR, CONFIGS, INDEXES_DIR, RetrievalConfig, load_corpus
from evals.groundtruth.embedder_cache import openai_embedder

TENANT = 0  # single public tenant; mirrors the cliente_id metadata production filters on


def _fingerprint_path(config: RetrievalConfig, indexes_dir: Path) -> Path:
    return indexes_dir / f"{config.index_name}.json"


def rebuild_command(config: RetrievalConfig) -> str:
    return f".venv/Scripts/python.exe -m evals.groundtruth.indexer --config {config.name}"


def corpus_sha256(corpus: dict[str, str]) -> dict[str, str]:
    """sha256 of each document's UTF-8 bytes, the same digest corpus/manifest.json records."""
    return {doc_id: hashlib.sha256(corpus[doc_id].encode("utf-8")).hexdigest() for doc_id in sorted(corpus)}


def read_fingerprint_file(config: RetrievalConfig, indexes_dir: Path = INDEXES_DIR) -> dict | None:
    """The whole fingerprint record of config's index, or None when no fingerprint file exists."""
    path = _fingerprint_path(config, indexes_dir)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def index_fingerprint(config: RetrievalConfig, indexes_dir: Path = INDEXES_DIR) -> dict | None:
    record = read_fingerprint_file(config, indexes_dir)
    return record["fingerprint"] if record is not None else None


def write_fingerprint(config: RetrievalConfig, corpus: dict[str, str], n_chunks: int,
                      indexes_dir: Path = INDEXES_DIR) -> Path:
    """Record what the table named config.index_name was built from.

    LanceDbRetriever refuses to open the table unless the config fingerprint and every corpus hash
    recorded here match the config and corpus it is handed, so this file is the index's contract.
    """
    path = _fingerprint_path(config, indexes_dir)
    path.write_text(json.dumps({
        "fingerprint": config.fingerprint(), "n_chunks": n_chunks, "docs": sorted(corpus),
        "corpus_sha256": corpus_sha256(corpus)}, indent=2), encoding="utf-8")
    return path


def build_index(config: RetrievalConfig, corpus: dict[str, str], embedder: Embedder,
                indexes_dir: Path = INDEXES_DIR) -> Path:
    indexes_dir.mkdir(parents=True, exist_ok=True)
    vector_db = LanceDb(uri=str(indexes_dir), table_name=config.index_name, embedder=embedder,
                        search_type=SearchType.vector, distance=Distance(config.distance), use_tantivy=False)
    if vector_db.exists():
        vector_db.drop()
    knowledge = Knowledge(vector_db=vector_db, max_results=config.max_results)
    reader = TextReader(chunking_strategy=FixedSizeChunking(chunk_size=config.chunk_size, overlap=config.chunk_overlap))
    for doc_id, text in corpus.items():
        knowledge.insert(name=doc_id, text_content=text,
                         metadata={"cliente_id": TENANT, "name": doc_id}, reader=reader)
    write_fingerprint(config, corpus, vector_db.get_count(), indexes_dir)
    return indexes_dir / f"{config.index_name}.lance"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--offline", action="store_true", help="fail on cache miss instead of calling the API")
    args = parser.parse_args()
    cfg = CONFIGS[args.config]
    emb = openai_embedder(cfg.embedder_id, cfg.embedder_dimensions, CACHE_DIR / "chunks", online=not args.offline)
    path = build_index(cfg, load_corpus(), emb)
    emb.save()
    fingerprint = json.loads(_fingerprint_path(cfg, INDEXES_DIR).read_text(encoding="utf-8"))
    print(f"built {path} with {fingerprint['n_chunks']} chunks")
