# A silently unreranked question in the 2026-09-15 rerank run

Task 23. The `rerank` config returns, for `r1-cdc-056`, different spans below rank 1 than the
2026-09-15 run that `results/report.md` and `results/significance.md` are built from. The cause is
not in the index or the candidate set. The 2026-09-15 record for that one question is plain vector
search, recorded under the `rerank` label, because agno 2.4.7's reranker swallowed its own failure.

## What the evidence shows

**The dense candidate set did not change.** The `chunk1500` config, which is the same table at the
same 1500/150 chunking, was rerun offline today and compared with the committed 2026-09-15
`results/chunk1500.json` per question: 0 of the 59 questions return a different ordered span list,
and `summary.overall`, `summary_no_leakage`, `summary_short_copy` and `by_category` are identical.
For `r1-cdc-056` the top 10 spans are the same ten spans in the same order.

**The 2026-09-15 rerank record for `r1-cdc-056` is that dense order.** Span for span, in order, the
2026-09-15 `rerank` top 10 for that question is the dense `chunk1500` top 10. Of the 59 questions in
that run, it is the only one whose top 10 equals the dense top 10; in the 2026-10-06 run, no question
does. A fallback necessarily produces the dense order, so at most one question in that run fell back.

**Forcing the fallback reproduces it exactly.** agno 2.4.7's `Reranker.rerank` wraps `_rerank` in a
bare `try`, logs `Error reranking documents: ... Returning original documents` and returns the
candidates untouched (`agno/knowledge/reranker/sentence_transformer.py:49-54`). With `_rerank` made
to raise, `LanceDbRetriever.search` on the committed table returns, for `r1-cdc-056`, exactly the
2026-09-15 list. With the reranker working, the same search returns exactly today's
`results/rerank.json` list. The two runs are the two branches of that `try`.

**A working reranker could not have produced the dense order.** The cross-encoder's scores over the
30 candidates are not monotone in distance rank: `cdc` chunk 52 scores 0.9827579855918884 at distance
rank 1, but `cpc` chunk 378 scores 0.7771536111831665 at distance rank 18, and `cdc` chunk 48 scores
0.030804989859461784 at distance rank 3. The model is also unchanged: the Hugging Face cache holds a
single `BAAI/bge-reranker-v2-m3` snapshot, `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, downloaded on
2026-09-15 between 10:44:23 and 10:46:59 and never replaced.

**What is not established: which exception fired.** The run was started in the background and only
its summary line survives in `.superpowers/sdd/2026-09-13-groundtruth/task-7-codex-rerun.log`, so no
stderr from it exists. The circumstantial evidence points at the first per-call `CrossEncoder`
construction: `r1-cdc-056` is the first of the 59 questions in that run, its recorded latency of
116305.24750001496 ms is the maximum and 2.56 times the run median of 45355.716299964115 ms, the
second question is the next slowest at 77228.5 ms, and the 2271071852-byte model was fetched into the
Hugging Face cache within minutes of that run. The timeline does not close to the second, though: the
recorded 116305.2 ms does not span the 156 seconds the download took. The trigger stays open.

## Hypotheses ruled out

- **Row order on disk.** The table was rebuilt twice into scratch directories from the committed
  corpus and cache, once inserting cdc, clt, cpc, lgpd and once inserting lgpd, cpc, clt, cdc. Both
  rebuilds and the committed table return bit-identical rows and bit-identical `_distance` values for
  all 59 questions, at depth 10, 30 and 100. Maximum absolute distance delta: 0.0.
- **A tie at the candidate boundary.** For `r1-cdc-056` the top 40 distances are 40 distinct values,
  and the gap between rank 30 (0.8877590894699097) and rank 31 (0.8905414342880249) is
  0.0027823448181152344, which is 46680 times the float32 spacing at that magnitude
  (5.960464477539063e-08).
- **An approximate index.** `list_indices()` on the table returns `[]` and the dataset has no
  `_indices` directory, so the 1054 rows are scanned exactly. agno never builds a vector index: the
  only `create_*_index` call in `agno/vectordb/lancedb/lance_db.py` is `create_fts_index`, at `:566`
  and `:592`, on the keyword and hybrid paths. `nprobes` is read at `:548` and `:579` but
  `LanceDbRetriever` does not pass it (`retriever.py:112-114`), so it stays `None`.
- **Changed chunk texts or embeddings.** All 1054 rows hold text exactly equal to the re-chunked
  committed corpus, and all 1054 vectors are bit-identical to the cached vector keyed on that text.
- **A library upgrade.** `requirements.txt` has pinned `lancedb==0.27.1` and `agno==2.4.7` since
  2026-03-19, including at commit 38822dfd of 2026-09-15. In the virtualenv, `lancedb`, `agno`,
  `pyarrow` 24.0.0 and `numpy` 2.4.4 were all installed on 2026-05-13 and never reinstalled;
  `sentence-transformers` 5.7.0 was installed on 2026-09-15 at 10:43:14, before that run.
- **The Task 22 reranker subclass.** It is not on this branch, and Task 22 measured it as producing
  byte-identical top 10s to agno's unpatched reranker.

## What it means for the published numbers

- **No published number changes.** `r1-cdc-056` scores 1.000 on recall@1, recall@5, recall@10, mrr
  and ndcg@10 under both orderings, because the golden passage is at rank 1 either way. Every
  per-question scored field and every aggregate is identical, so every `rerank` figure in
  `results/report.md` and `results/significance.md` stands. `results/failures.md` lists only the five
  production misses and does not mention this question.
- **One published number was shaped by the failure.** The `rerank` row's `p50 search ms` of 45356 in
  `results/report.md` is the median of the 59 latencies, and the failed search contributed the
  slowest of them, 116305.2 ms. Being the maximum, it barely moves the median: dropping it gives
  44891, and setting it to a typical 40000 ms gives 44426. The field is informational, not gated.
- **What is wrong is the provenance, not the value.** One of the 59 rows behind the published
  `rerank` numbers was produced by plain vector search, and nothing in the artifact says so.
- **The index is reproducible; a reranked run is not.** Rebuilding offline from the committed corpus
  and cache reproduces the committed table exactly, in either insertion order, for all 59 questions
  at depth 100. The `rerank` run is a different matter: agno's reranker can fall back silently, and
  the harness records nothing that distinguishes a fallback from a successful rerank, so the same
  command on the same inputs can produce two different `results/rerank.json` files.
- **The gate would not have caught it.** `tests/test_gate.py` runs the `production` config, and
  `ia/retrieval_config.py:29` sets `RERANKER = None`, so the gate never enters the reranker path at
  all. Even run against `rerank`, it compares only recall@10 and mrr, both unchanged here, against
  tolerances of 0.01 and 0.02. The gate does catch a changed index fingerprint or corpus hash, a
  stale query cache, a changed golden set size, and a recall@10 or mrr regression on production; it
  does not look at recall@1, ndcg@10, latency, candidate composition below rank 10, or any config
  other than production.

## Pinned by

`tests/test_rerank_fallback.py`: a reranker that returns its candidates unchanged yields exactly the
distance order, and `LanceDbRetriever` records the same `last_requested_limit`, `last_survivors` and
`last_shortfall` either way. The fourth test pins agno's except branch directly and is skipped where
`sentence-transformers` is not installed, which includes CI.

No API call was made for any of this: `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` were empty, every
embedder ran with `online=False`, and the cross-encoder was loaded with `HF_HUB_OFFLINE=1`. Nothing
was written under `indexes/` or `cache/`; every rebuild and rerun went to a scratch directory.
