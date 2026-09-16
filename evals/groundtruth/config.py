from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ia import retrieval_config as prod

GROUNDTRUTH_DIR = Path(__file__).resolve().parent
CORPUS_DOCS_DIR = GROUNDTRUTH_DIR / "corpus" / "docs"
CORPUS_MANIFEST = GROUNDTRUTH_DIR / "corpus" / "manifest.json"
GOLDEN_SET = GROUNDTRUTH_DIR / "golden" / "golden_set.jsonl"
CANDIDATES = GROUNDTRUTH_DIR / "golden" / "candidates.jsonl"
DECISIONS = GROUNDTRUTH_DIR / "golden" / "decisions.jsonl"
TRIAGE = GROUNDTRUTH_DIR / "golden" / "triage.jsonl"
JUDGMENTS = GROUNDTRUTH_DIR / "golden" / "judgments.jsonl"
CACHE_DIR = GROUNDTRUTH_DIR / "cache"
INDEXES_DIR = GROUNDTRUTH_DIR / "indexes"
RESULTS_DIR = GROUNDTRUTH_DIR / "results"
CALIBRATION_SAMPLE = GROUNDTRUTH_DIR / "golden" / "calibration_sample.json"
HUMAN_LABELS = GROUNDTRUTH_DIR / "golden" / "human_labels.jsonl"
CALIBRATION_REPORT = RESULTS_DIR / "golden_calibration.md"
CONSENSUS_REPORT = RESULTS_DIR / "golden_consensus.md"
BASELINE = GROUNDTRUTH_DIR / "baseline.json"
OUT_OF_SCOPE = GROUNDTRUTH_DIR / "generation" / "out_of_scope.jsonl"
OUT_OF_SCOPE_CHECK = GROUNDTRUTH_DIR / "generation" / "out_of_scope_check.jsonl"
OUT_OF_SCOPE_REPORT = RESULTS_DIR / "out_of_scope_check.md"

# Task 9b: generation layer (agent answers scored separately from retrieval)
GENERATION_DIR = GROUNDTRUTH_DIR / "generation"
ANSWERS = GENERATION_DIR / "answers.jsonl"
SCORES = GENERATION_DIR / "scores.json"
GENERATION_REPORT = RESULTS_DIR / "generation.md"
GENERATION_RUNTIME_DIR = GROUNDTRUTH_DIR / "runtime" / "generation"
SAMPLE_SIZE = 30
SAMPLE_SEED = 7


def load_corpus() -> dict[str, str]:
    """Return {doc_id: normalized text} for every committed corpus document."""
    corpus = {}
    for path in sorted(CORPUS_DOCS_DIR.glob("*.txt")):
        corpus[path.stem] = path.read_text(encoding="utf-8")
    if not corpus:
        raise FileNotFoundError(f"No corpus documents in {CORPUS_DOCS_DIR}; run build_corpus")
    return corpus


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    chunk_size: int
    chunk_overlap: int
    search_type: str
    reranker: Optional[str]
    rerank_candidates: int = 30
    embedder_id: str = prod.EMBEDDER_ID
    embedder_dimensions: int = prod.EMBEDDER_DIMENSIONS
    distance: str = prod.DISTANCE
    max_results: int = prod.MAX_RESULTS

    @property
    def index_name(self) -> str:
        """Chunking and embedder define the index; search type and reranker are query-time.

        The dimension is part of the name because models such as text-embedding-3-small support
        dimension reduction, so the same id at two dimensions produces two incompatible tables.
        """
        return f"c{self.chunk_size}_o{self.chunk_overlap}_{self.embedder_id}_d{self.embedder_dimensions}"

    def fingerprint(self) -> dict:
        return {"chunk_size": self.chunk_size, "chunk_overlap": self.chunk_overlap,
                "embedder_id": self.embedder_id, "embedder_dimensions": self.embedder_dimensions}

    def as_dict(self) -> dict:
        return asdict(self)


PRODUCTION = RetrievalConfig(
    name="production", chunk_size=prod.CHUNK_SIZE, chunk_overlap=prod.CHUNK_OVERLAP,
    search_type=prod.SEARCH_TYPE, reranker=prod.RERANKER,
)
CONFIGS: dict[str, RetrievalConfig] = {c.name: c for c in [
    PRODUCTION,
    RetrievalConfig("chunk1500", 1500, 150, "vector", None),
    RetrievalConfig("chunk800", 800, 100, "vector", None),
    # hybrid and rerank use the chunk winner of the Task 7 comparison, see results/notes.md
    RetrievalConfig("hybrid", 1500, 150, "hybrid", None),
    RetrievalConfig("rerank", 1500, 150, "vector", "bge-reranker-v2-m3"),
]}
