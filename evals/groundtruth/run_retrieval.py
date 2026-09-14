# evals/groundtruth/run_retrieval.py
"""Run one or more retrieval configs over the golden set and write results/<config>.json.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.run_retrieval --config production [--offline] [--write-baseline]"""
import argparse
import json
import sys
import time
from pathlib import Path

from evals.groundtruth.config import BASELINE, CACHE_DIR, CONFIGS, GOLDEN_SET, RESULTS_DIR, RetrievalConfig, load_corpus
from evals.groundtruth.embedder_cache import openai_embedder
from evals.groundtruth.golden.leakage import NGRAM_FLAG
from evals.groundtruth.golden.schema import GoldenItem, load_golden
from evals.groundtruth.retriever import build_retriever
from evals.groundtruth.scorers import Span, aggregate, score_item


def run_config(config: RetrievalConfig, golden: list[GoldenItem], corpus: dict[str, str], embedder) -> dict:
    retriever = build_retriever(config, corpus, embedder)
    items = []
    for item in golden:
        embedder.get_embedding(item.question)  # warm the cache outside the timer: latency measures search, not the embedding API
        t0 = time.perf_counter()
        hits = retriever.search(item.question, k=config.max_results)
        latency_ms = (time.perf_counter() - t0) * 1000
        retrieved = [Span(h.doc_id, h.start, h.end) for h in hits]
        passages = [Span(p.doc_id, p.start, p.end) for p in item.passages]
        items.append({"id": item.id, "category": item.category, **score_item(retrieved, passages),
                      "no_leakage": bool(item.leakage and item.leakage.no_leakage),
                      "short_copy": bool(item.leakage and item.leakage.max_shared_ngram < NGRAM_FLAG),
                      "latency_ms": latency_ms, "retrieved": [[s.doc_id, s.start, s.end] for s in retrieved]})
    return {"config": config.as_dict(), "n_golden": len(golden), "items": items, "summary": aggregate(items),
            "summary_no_leakage": aggregate([row for row in items if row["no_leakage"]]),
            "summary_short_copy": aggregate([row for row in items if row["short_copy"]])}


def write_results(result: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{result['config']['name']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", nargs="+", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    golden, corpus = load_golden(GOLDEN_SET), load_corpus()
    for name in args.config:
        cfg = CONFIGS[name]
        emb = openai_embedder(cfg.embedder_id, cfg.embedder_dimensions, CACHE_DIR / "queries", online=not args.offline)
        result = run_config(cfg, golden, corpus, emb)
        emb.save()
        path = write_results(result)
        print(name, json.dumps(result["summary"]["overall"]), "->", path)
        if args.write_baseline and name == "production":
            BASELINE.write_text(json.dumps({"config": "production", "n_golden": len(golden),
                                            "recall@10": result["summary"]["overall"]["recall@10"],
                                            "index_fingerprint": cfg.fingerprint()}, indent=2), encoding="utf-8")
