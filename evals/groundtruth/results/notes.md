# Task 7 notes: chunk size, hybrid search and reranker

## 1. Hit rule

Since 2026-09-14, a chunk hits a golden passage when it covers at least 50% of the passage, or when
at least 50% of the chunk lies inside the passage (bidirectional hit rule, `is_hit` in `scorers.py`).
Under the old, one-directional rule (overlap of the passage only), a chunk shorter than half a
passage could never be a hit no matter how fully it sat inside it. Reproduced with an offline oracle
over the chunk800 chunking (`evals/groundtruth/runtime/oracle_old_rule.py`, not committed): under the
old rule chunk800 could reach only 53 of 59 golden passages, and 17 of the 20 no-leakage passages. The
6 unreachable items are `r1-cdc-062`, `r1-cdc-066`, `r1-clt-042`, `r1-clt-047`, `r1-lgpd-071`,
`r1-lgpd-072`. Production metrics recomputed under the new rule are identical to `baseline.json`.

## 2. Summary table

| config | chunk size/overlap | search type | reranker | n_chunks | recall@10 full | recall@10 no-leak | recall@10 short-copy | MRR (full) | nDCG@10 (full) | p50 search ms |
|---|---|---|---|---|---|---|---|---|---|---|
| production | 5000/0 | vector | none | 285 | 0.915 | 0.750 | 0.898 | 0.594 | 0.675 | 12 |
| chunk1500 | 1500/150 | vector | none | 1054 | 0.932 | 0.900 | 0.918 | 0.811 | 0.842 | 14 |
| chunk800 | 800/100 | vector | none | 2035 | 0.915 | 0.900 | 0.918 | 0.729 | 0.775 | 16 |
| hybrid | 1500/150 | hybrid | none | 1054 | 0.966 | 0.900 | 0.959 | 0.806 | 0.847 | 17 |
| rerank | 1500/150 | vector | bge-reranker-v2-m3 | 1054 | 0.966 | 0.900 | 0.959 | 0.921 | 0.933 | 45356 |

## 3. Winner

hybrid and rerank use chunk 1500/150, the winner of step 1 by recall@10 (0.932).

Full-set per-metric winner: rerank on recall@1 (0.881), recall@5 (0.966), MRR (0.921) and nDCG@10
(0.933); hybrid and rerank tie on recall@10 (0.966).

No-leakage subset per-metric winner: rerank on recall@1 (0.750), MRR (0.817) and nDCG@10 (0.838);
chunk1500, chunk800, hybrid and rerank tie on recall@5 and recall@10 (0.900), all above production
(0.750).

## 4. Ingestion cost per index

Chunks and embedding tokens counted with tiktoken `cl100k_base` over the chunk texts from
`chunk_offsets` (script: `evals/groundtruth/runtime/count_tokens.py`, not committed). Cost at $0.02
per 1M tokens, citing developers.openai.com text-embedding-3-small model page, fetched 2026-09-14.

| config | n_chunks | tokens | cost |
|---|---|---|---|
| production | 285 | 434515 | $0.00869 |
| chunk1500 | 1054 | 483330 | $0.00967 |
| chunk800 | 2035 | 497704 | $0.00995 |

Counts match the controller's figures exactly; no difference to report.

## 5. Trade-offs

Each comparison below gives recall@1, recall@10 and MRR on the full set (59 items, one item worth
about 0.017 of recall) and on the no-leakage subset (20 items, one item worth 0.05 of recall), and
names every metric that gets worse. Item counts come from `results/*.json`
(`evals/groundtruth/runtime/item_counts.py`, not committed). Latency is the observed p50 only.

**Production against chunk1500.** Full set: recall@1 rises from 0.373 to 0.712 (22 to 42 of 59
items), recall@10 rises from 0.915 to 0.932 (54 to 55 of 59), MRR rises from 0.594 to 0.811.
No-leakage subset: recall@1 rises from 0.400 to 0.650 (8 to 13 of 20 items), recall@10 rises from
0.750 to 0.900 (15 to 18 of 20), MRR rises from 0.575 to 0.742. Every one of these six values
improves; there is no regression in this comparison.

**chunk800 against chunk1500.** Full set: recall@1 is lower (0.627 vs 0.712, 37 vs 42 of 59 items),
recall@10 is lower (0.915 vs 0.932, 54 vs 55 of 59), MRR is lower (0.729 vs 0.811). No-leakage
subset: recall@1 does not change (0.650 vs 0.650, 13 of 20 items both), recall@10 does not change
(0.900 vs 0.900, 18 of 20 items both), MRR is marginally lower (0.729 vs 0.742). chunk800 does not
beat chunk1500 on any of these six values, while roughly doubling the chunk count from 1054 to 2035.

**Hybrid against dense chunk1500.** Full set: recall@1 is lower (0.695 vs 0.712, 41 vs 42 of 59
items), recall@10 is higher (0.966 vs 0.932, 57 vs 55 of 59), MRR is lower (0.806 vs 0.811).
No-leakage subset: recall@1 is lower (0.500 vs 0.650, 10 vs 13 of 20 items), recall@10 does not
change (0.900 vs 0.900, 18 of 20 items both), MRR is lower (0.667 vs 0.742). Hybrid trades a
full-set recall@10 gain of 2 items for a full-set recall@1 loss of 1 item and a no-leakage recall@1
loss of 3 items; p50 search latency is 17 ms against dense chunk1500's 14 ms, an observed value with
no isolated cause in this run.

**Reranker against dense chunk1500.** Full set: recall@1 is higher (0.881 vs 0.712, 52 vs 42 of 59
items), recall@10 is higher (0.966 vs 0.932, 57 vs 55 of 59), MRR is higher (0.921 vs 0.811).
No-leakage subset: recall@1 is higher (0.750 vs 0.650, 15 vs 13 of 20 items), recall@10 does not
change (0.900 vs 0.900, 18 of 20 items both), MRR is higher (0.817 vs 0.742). Every one of these six
values improves or holds; the cost is latency, because the reranker reloads its model on every call
(section 7), and p50 search rises from 14 ms to 45356 ms.

## 6. Hybrid facts

`hybrid` uses agno 2.4.7's native LanceDB full-text search without tantivy (`use_tantivy=False`),
built over the `payload` column, which stores each row's JSON name and metadata. There is no
Portuguese stemming. `create_fts_index("payload", use_tantivy=False, replace=True)` ran on the first
timed search and did not fail; its latency is folded into that query's timing, and one slow query
can shift the p50 over 59 queries by at most one rank position. The winner (chunk1500) was not production, so no post-hybrid production re-check was
needed; `git status --short` after the hybrid run showed only the expected untracked
`calibration_sample.json`.

## 7. Reranker facts

agno 2.4.7's `SentenceTransformerReranker._rerank` (`agno/knowledge/reranker/sentence_transformer.py:22`)
constructs a new `CrossEncoder` on every call, so every timed rerank search in this run includes
loading `BAAI/bge-reranker-v2-m3` from disk. This was measured as is, not patched or cached. The
machine has no GPU; sentence-transformers, tokenizers and torch loaded without any Application Control
block, and the model downloaded from Hugging Face without incident.

## 8. Latency note

p50 search ms is wall-clock time inside `retriever.search`, with the query embedding already computed
outside the timer, measured on the machine that ran it. It is informational and not gated.
