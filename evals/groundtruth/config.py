from pathlib import Path

GROUNDTRUTH_DIR = Path(__file__).resolve().parent
CORPUS_DOCS_DIR = GROUNDTRUTH_DIR / "corpus" / "docs"
CORPUS_MANIFEST = GROUNDTRUTH_DIR / "corpus" / "manifest.json"
GOLDEN_SET = GROUNDTRUTH_DIR / "golden" / "golden_set.jsonl"
CANDIDATES = GROUNDTRUTH_DIR / "golden" / "candidates.jsonl"
DECISIONS = GROUNDTRUTH_DIR / "golden" / "decisions.jsonl"
CACHE_DIR = GROUNDTRUTH_DIR / "cache"
INDEXES_DIR = GROUNDTRUTH_DIR / "indexes"
RESULTS_DIR = GROUNDTRUTH_DIR / "results"
BASELINE = GROUNDTRUTH_DIR / "baseline.json"


def load_corpus() -> dict[str, str]:
    """Return {doc_id: normalized text} for every committed corpus document."""
    corpus = {}
    for path in sorted(CORPUS_DOCS_DIR.glob("*.txt")):
        corpus[path.stem] = path.read_text(encoding="utf-8")
    if not corpus:
        raise FileNotFoundError(f"No corpus documents in {CORPUS_DOCS_DIR}; run build_corpus")
    return corpus
