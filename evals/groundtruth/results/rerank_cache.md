# Reranker latency: loading the cross-encoder once instead of once per search

## What changed

`evals/groundtruth/reranker.py` subclasses agno's `SentenceTransformerReranker` so the cross-encoder
comes from a module-level cache instead of the `CrossEncoder(...)` that agno 2.4.7 constructs inside
every call at `agno/knowledge/reranker/sentence_transformer.py:22`; the scoring, sorting and `top_n`
are agno's, copied unchanged.

## Latency, before and after

Before: the `rerank` row of `results/report.md`, which is the Task 7 run. After: a rerun of
`python -m evals.groundtruth.run_retrieval --config rerank --offline` over the same 59 golden
questions, on the machine described below. Both are wall-clock time inside `retriever.search` with
the query embedding already computed, the same measurement `results/report.md` prints.

| run | p50 | p95 | max | min | sum over 59 questions |
|---|---|---|---|---|---|
| before, model loaded per search | 45356 ms | 67280 ms | 116305 ms | 27744 ms | 2696.5 s |
| after, model loaded once | 34730 ms | 39894 ms | 45114 ms | 30802 ms | 2079.2 s |

p95 is the nearest-rank percentile over the 59 per-question `latency_ms` values in
`results/rerank.json`; the runner itself reports only the per-question values, and
`results/report.md` reports only the p50.

The shape of the two runs is the evidence that the model is now loaded once. Before, the first
question cost 116305 ms, 71414 ms more than the p50 of the other 58 (44891 ms), and every later
question still paid its own load. After, the first question cost 38910 ms, 4216 ms more than the p50
of the other 58 (34694 ms), and that gap is the single load.

**The per-call reload was never the whole cost.** It is 10626 ms of the 45356 ms p50, about 23%. The
34730 ms that remain are the cross-encoder's forward pass over the 30 candidates of each query on
this CPU. The previous reading of this number in both READMEs, that p50 is 45356 ms because agno
reloads the model, named a real cause but implied it was the only one; it was not.

## Ranking, before and after

Before from the `rerank` row of `results/report.md`, after from the rerun's
`results/rerank.json`. These must be identical, because this task changed only when the model is
loaded, not how any document is scored:

| metric | before | after |
|---|---|---|
| recall@1 | 0.881 | 0.881 |
| recall@10 | 0.966 | 0.966 |
| mrr | 0.921 | 0.921 |
| ndcg@10 | 0.933 | 0.933 |

They are identical, and not only at the 3 decimals `results/report.md` prints: the two runs agree bit
for bit in full float precision on all five metrics, on the full set, on the no-leakage subset (n=20)
and on the short-copy subset (n=49). recall@5 is 0.966 in both. All 59 per-question metric values are
equal. `results/report.md` was not regenerated, and `results/significance.md` and
`results/failures.md` still rebuild byte for byte from the new `results/rerank.json`.

### One question's result order moved, and it is not from this change

Of the 59 questions, 58 return exactly the spans the committed run returned, in the same order.
`r1-cdc-056` returns a different set below rank 1. Its rank 1 is the same chunk and is the golden
passage, so its recall@1, recall@5, recall@10, mrr and ndcg@10 are 1.000 in both runs, which is why
no metric moves.

This task did not cause it. Running agno's unpatched `SentenceTransformerReranker` and the harness
subclass against the same index today gives byte-identical top 10s for that question, and both
differ from the committed run in the same way. The reranking scores for it are not near-ties
either (rank 1 0.983, rank 2 0.777, rank 3 0.512), and three repeats in one process give the same
order, so this is not float noise in the cross-encoder. The candidate set the vector search hands
the reranker for that question has changed at some point between the Task 7 run and today. The cause
was not established here and is left as a finding.

## Machine

The after numbers were measured on Windows 11 Home Single Language 10.0.26200, AMD Ryzen 7 5825U,
8 physical cores and 16 logical, 15.4 GB RAM, no CUDA GPU (`torch.cuda.is_available()` is False),
Python 3.12.10, torch 2.11.0+cpu, sentence-transformers 5.7.0, agno 2.4.7. Latency is machine
dependent and informational, not gated. The before numbers come from the Task 7 run recorded in
`results/report.md`, measured on the same machine.

The run made no API call and downloaded nothing: `--offline` leaves the embedder with no inner
client, so a query embedding that is not in the committed cache raises instead of calling OpenAI,
and the cross-encoder is built with `local_files_only=True` against the Hugging Face cache, which
held the same 14 files and the same 2293242148 bytes before and after.

## What this does not fix

agno still constructs a `CrossEncoder` inside every `_rerank` call for anyone using
`SentenceTransformerReranker` directly, including `ia/` if it ever sets `RERANKER`; the cache lives
in the harness only, and nothing in the library changed.
