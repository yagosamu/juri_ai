# Groundtruth

**Portuguese version:** [README.pt-br.md](README.pt-br.md)

Retrieval and generation evaluation for JuriAI's RAG over 4 public Brazilian statutes and 59 questions selected by two-model consensus. Production adopted the measured winner of that comparison, chunk1500, and now runs at recall@10 0.932 and mrr 0.811 (`results/adoption.md`). The best configurations measured reach recall@10 of 0.966 (hybrid search and reranker, tied).

## Results

### Retrieval

Five configurations run over the same 59 golden questions.

**`production` in every table and comparison below is the pre-adoption configuration, 5000/0.** These tables are the historical measurement that motivated the change and are kept as they were; since `results/adoption.md`, `ia/retrieval_config.py` runs the `chunk1500` parameters, 1500/150, so the live production numbers are the `chunk1500` row.

| config | chunk size/overlap | search type | reranker | n_chunks |
|---|---|---|---|---|
| production | 5000/0 | vector | none | 285 |
| chunk1500 | 1500/150 | vector | none | 1054 |
| chunk800 | 800/100 | vector | none | 2035 |
| hybrid | 1500/150 | hybrid | none | 1054 |
| rerank | 1500/150 | vector | bge-reranker-v2-m3 | 1054 |

Source: `results/notes.md`, section 2.

All 59 questions:

| config | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 | p50 search ms |
|---|---|---|---|---|---|---|
| chunk1500 | 0.712 | 0.932 | 0.932 | 0.811 | 0.842 | 14 |
| chunk800 | 0.627 | 0.898 | 0.915 | 0.729 | 0.775 | 16 |
| hybrid | 0.695 | 0.949 | 0.966 | 0.806 | 0.847 | 17 |
| production | 0.373 | 0.864 | 0.915 | 0.594 | 0.675 | 12 |
| rerank | 0.881 | 0.966 | 0.966 | 0.921 | 0.933 | 45356 |

p50 search ms: wall-clock time inside retriever.search with the query embedding already computed, on the machine that ran it; informational, not gated.

Source: `results/report.md`.

no-leakage subset (spec): no judge rated leakage heavy and the longest copied run is under 5 tokens

| config | n | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 |
|---|---|---|---|---|---|---|
| chunk1500 | 20 | 0.650 | 0.900 | 0.900 | 0.742 | 0.781 |
| chunk800 | 20 | 0.650 | 0.900 | 0.900 | 0.729 | 0.771 |
| hybrid | 20 | 0.500 | 0.900 | 0.900 | 0.667 | 0.726 |
| production | 20 | 0.400 | 0.750 | 0.750 | 0.575 | 0.621 |
| rerank | 20 | 0.750 | 0.900 | 0.900 | 0.817 | 0.838 |

Source: `results/report.md`.

short-copy subset (robustness view): the longest copied run is under 5 tokens; judge leakage labels are ignored

| config | n | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 |
|---|---|---|---|---|---|---|
| chunk1500 | 49 | 0.694 | 0.918 | 0.918 | 0.793 | 0.825 |
| chunk800 | 49 | 0.612 | 0.898 | 0.918 | 0.720 | 0.769 |
| hybrid | 49 | 0.673 | 0.939 | 0.959 | 0.787 | 0.831 |
| production | 49 | 0.388 | 0.837 | 0.898 | 0.600 | 0.675 |
| rerank | 49 | 0.878 | 0.959 | 0.959 | 0.915 | 0.926 |

Source: `results/report.md`.

recall@10 by category

| config | conceito | fato_pontual | procedimento |
|---|---|---|---|
| chunk1500 | 0.818 (n=11) | 0.944 (n=18) | 0.967 (n=30) |
| chunk800 | 0.727 (n=11) | 0.944 (n=18) | 0.967 (n=30) |
| hybrid | 0.909 (n=11) | 0.944 (n=18) | 1.000 (n=30) |
| production | 0.909 (n=11) | 0.944 (n=18) | 0.900 (n=30) |
| rerank | 0.909 (n=11) | 0.944 (n=18) | 1.000 (n=30) |

Source: `results/report.md`.

On the full set, rerank has the highest recall@1 (0.881), recall@5 (0.966), MRR (0.921) and nDCG@10 (0.933), and ties with hybrid on recall@10 (0.966). On the no-leakage subset, chunk1500, chunk800, hybrid and rerank tie on recall@10 (0.900), all above production (0.750). The reranker's gain costs latency: p50 search rises from 14 ms to 45356 ms (see [What did not work](#what-did-not-work-and-findings)). Source: `results/notes.md`, sections 3 and 5.

See `results/significance.md` for the pre-registered bootstrap intervals and paired tests: chunk1500's recall@1 and MRR gains over production are significant after Holm correction (Holm p=0.0004 and 0.0010), but its recall@10 gain is not (Holm p=1.0000); hybrid's recall@10 gain over chunk1500 is not significant (Holm p=1.0000); rerank's MRR gain over chunk1500 is significant (Holm p=0.0216), but its recall@1 gain is not, after Holm correction (Holm p=0.0638).

### Generation

The real JuriAI agent (gpt-4o) answered a sample of 30 golden questions (seed 7) and 10 out-of-scope questions, under the adopted 1500/150 retrieval config and with the Task 20 abstention instruction in `JuriAI.INSTRUCTIONS`. Faithfulness and answer relevancy are scored by DeepEval with gpt-4.1-mini as the judge model; abstention by gpt-4.1 and claude-haiku-4-5 together.

**The agent now abstains on 10 of 10 out-of-scope questions.** Before, under 5000/0 and with no abstention instruction, it abstained on 0 of the 7 it completed and answered them from general knowledge. The chunking and the instruction changed in the same step, so neither result is attributable to one of them alone.

Before and after, side by side, with the tokens-per-turn and unscored counts: `results/generation_adoption.md`. The pre-adoption measurement is preserved whole in `results/generation_pre_adoption.md`, with `generation/answers_pre_adoption.jsonl` and `generation/scores_pre_adoption.json`.

| category | faithfulness mean | faithfulness n | relevancy mean | relevancy n |
|---|---|---|---|---|
| conceito | 0.960 | 7 | 0.969 | 8 |
| fato_pontual | 0.907 | 8 | 0.954 | 8 |
| procedimento | 0.946 | 13 | 0.983 | 14 |
| overall | 0.938 | 28 | 0.971 | 30 |

No retrieval, excluded from the faithfulness mean: 1. Run failed, excluded from both means: 0. Not scored by the judge, excluded from the faithfulness mean: 1, because a content filter refused that one faithfulness call. Against the pre-adoption 0.952 (n=29) and 0.983 (n=30), both means move down slightly; one pass each with no repeats, so that is not evidence of a change in quality either way.

| label | count |
|---|---|
| abstained | 10 of 10 completed runs |
| answered | 0 of 10 completed runs |
| disagreement | 0 of 10 completed runs |
| unverified | 0 of 10 completed runs |
| run failed | 0 of 10 out-of-scope questions |

**No run failed, and no turn came close to the rate limit.** Input tokens per turn fell from a mean of 15004.2 and a maximum of 40912 to a mean of 5479.8 and a maximum of 6257, against a Tier 1 limit of 30,000 gpt-4o tokens per minute. Before, 2 completed turns and all 3 failed ones were at or above that limit, so one turn could exhaust the per-minute budget by itself; after, none can. Four rows did fail on transient rate limits in the first pass of this run and were rerun with `--only`, which refuses any id that is not currently a failed run, so the sample was restored rather than reselected.

**One in-scope question was refused**, `r1-cdc-060`: the agent searched, retrieved a context, and still said it found nothing in the knowledge base. That is 1 of 30, and the two means cannot detect it, because DeepEval scored that refusal 1.00 on both faithfulness and relevancy, which raises both published means instead of lowering them: without that row, faithfulness is 0.9358363858363858 over n=27 instead of 0.9381279434850863 over n=28, and relevancy 0.9703359858532272 over n=29 instead of 0.9713247863247862 over n=30. Since Task 21 an offline phrasing detector measures both directions and both counts are gated: 1 refusal among the 30 golden rows and 10 detected abstentions among the 10 out-of-scope rows, the latter agreeing with the two-judge labels on 10 of 10. Full reasoning in `results/generation_adoption.md`, counts and what they miss in `results/abstention.md`.

Answers that searched the knowledge base: 39 of 40. Measured cost of the generation run: $0.8319 in total, down from $1.8735, excluding agno's background memory-update calls and the DeepEval calls made during the crashed first pass. Source: `results/generation.md`.

## Adopted change

**chunk1500 dense is what production runs now.** `ia/retrieval_config.py` sets `CHUNK_SIZE = 1500` and `CHUNK_OVERLAP = 150`; nothing else in that module changed. Against the pre-adoption 5000/0 configuration, chunk1500 raises recall@1 from 0.373 to 0.712 and MRR from 0.594 to 0.811; `results/significance.md` finds both gaps significant after Holm correction (recall@1: b=23, c=3, Holm p=0.0004; MRR difference 0.216 [0.119, 0.314], Holm p=0.0010). The recall@10 gain, 0.915 to 0.932, is not significant (b=3, c=2, Holm p=1.0000). It costs a little more: p50 search rises from 12 ms to 14 ms, the index grows from 285 to 1054 chunks, and ingestion rises from 434515 to 483330 tokens ($0.00869 to $0.00967). Full record, including the new baseline and what this change does not measure: `results/adoption.md`. Sources: `results/notes.md`, sections 2 and 4, and `results/significance.md`.

**Hybrid** is an option when recall@10 matters more than the first result. Against chunk1500, `results/significance.md` finds the full-set recall@10 gain (0.932 to 0.966, b=2, c=0) not significant after Holm correction (Holm p=1.0000), and neither the recall@1 nor the MRR change is significant either. On the no-leakage subset, hybrid lowers recall@1 (0.650 to 0.500) and MRR (0.742 to 0.667) against chunk1500, though neither drop is significant at n=20 (Holm p=1.0000 and 0.8888).

**Rerank** has the best ranking numbers on the full set (recall@1 0.881, MRR 0.921), and its MRR gain over chunk1500 is significant (difference 0.110 [0.035, 0.192], Holm p=0.0216); its recall@1 gain is not significant after Holm correction (Holm p=0.0638). It is not a candidate until the per-call model reload is fixed: p50 search is 45356 ms, because agno 2.4.7 reloads `BAAI/bge-reranker-v2-m3` from disk on every call (see [What did not work](#what-did-not-work-and-findings)).

**Adoption cost, as paid.** The committed index and `baseline.json` were rebuilt offline from the local chunk embedding cache, with no API call. Stored documents are a different matter: no code path reindexes a `Documentos` row that is already in LanceDB (see [What did not work](#what-did-not-work-and-findings)). Production's `render.yaml` sets `DATA_DIR=/tmp/juri-ai` (lines 17 and 18), so the LanceDB index lives on ephemeral storage and does not survive a deploy or restart.

**Transfer caveat.** The comparison ran on 4 public statutes, while production documents are petitions and contracts passed through OCR. The gain is measured on this corpus only.

**Generation under the new chunking is now measured.** Task 20 reran it at 1500/150, together with an abstention instruction added to the agent in the same step: `results/generation_adoption.md` has the before and after, and `results/generation.md` is the current report. What is still not measured is either change on its own, since the two moved together.

## How it works

```mermaid
flowchart LR
    A["corpus: 4 statutes, normalized"] --> B["Knowledge.insert + FixedSizeChunking"]
    B --> C["LanceDB"]
    C --> D["LanceDb.search + cliente_id post-filter"]
    D --> E["chunks as character spans"]
    E --> F["scorers: bidirectional hit rule"]
    F --> G["results/report.md"]
    H["committed production index + query embedding cache"] --> I["pytest gate"]
    I --> J["compare with baseline.json"]
```

The indexer (`indexer.py`) inserts the corpus through the same agno path production uses. The retriever (`retriever.py`) calls the same `LanceDb.search`, maps each returned chunk back to a `[start, end)` character span in the normalized statute text, and the scorers (`scorers.py`) compare those spans with the golden passages.

## Golden set

### How the 59 questions were chosen

1. `golden/candidates.py` sampled 80 statute articles (cpc 30, clt 25, cdc 15, lgpd 10) and asked gpt-4.1-mini for one lawyer-style question per article.
2. `golden/triage.py` computed deterministic leakage signals and found competitor articles by two methods independent of the system under test: BM25 and text-embedding-3-large, top 5 each.
3. `golden/judges.py` ran two judges from different vendors, gpt-4.1 and claude-haiku-4-5, on the same evidence with rubric v2. Each judge is blind to the other and to the stored category.
4. `golden/consensus.py` admits a candidate only when both judges say the article alone fully answers the question, no judge names a competitor that fully answers it, the question cites no source, and both verdicts exist. The category is the majority of the generator and the two judges. Leakage never excludes; it is recorded.

Candidates: 80. Included: 59. Excluded: 21. There was no human legal review.

| exclusion reason | candidates |
|---|---|
| also_answered_by | 16 |
| answerable | 4 |
| category_no_majority | 4 |
| cites_source | 1 |
| judge_missing | 2 |

A candidate can have more than one reason.

| category | items |
|---|---|
| conceito | 11 |
| fato_pontual | 18 |
| procedimento | 30 |

No-leakage subset: 20 of 59 items, where no judge rated leakage heavy and the longest copied run is under 5 tokens.

Source: `results/golden_consensus.md`.

### Agreement between judges

| field | n | agreement | Cohen's kappa |
|---|---|---|---|
| answerable | 78 | 0.962 | 0.381 |
| also answered by any | 78 | 0.833 | 0.199 |
| leakage | 78 | 0.282 | -0.077 |
| category | 78 | 0.692 | 0.468 |

Source: `results/golden_consensus.md`.

The judges disagree on leakage at worse than chance (kappa -0.077). That disagreement is why two subsets are reported: the no-leakage subset uses both judges' labels, and the short-copy subset ignores them.

### Out-of-scope questions

The generation layer also uses 10 out-of-scope questions. `generation/out_of_scope_check.py` shows each question to gpt-4.1 and claude-haiku-4-5 together with the union of its BM25 top 5 and text-embedding-3-large top 5 articles. A question counts as out of scope only when both judges agree that none of those articles contains any part of the answer. The first run flagged oos-05 and oos-07 as answerable; those two questions were replaced, keeping their ids, and the re-run found 10 of 10 out of scope. Sources: `results/out_of_scope_check.md` and commit `c452ab4`.

## Design decisions

**(a) Passages are character spans, not chunk ids.** A golden passage is a `[start, end)` range in the normalized statute text, so any chunking or vector store can be scored against the same golden set. What it cost: the original hit rule (a chunk must cover 50% of a passage) meant a chunk shorter than half a passage could never hit it. Under that rule chunk800 could reach only 53 of 59 golden passages, and 17 of the 20 no-leakage passages. The rule became bidirectional before the chunk comparison: a chunk also hits when at least 50% of the chunk lies inside the passage. Production metrics are identical under both rules. Source: `results/notes.md`, section 1.

**(b) CI runs offline.** The production LanceDB index and the query embedding cache are committed, so the gate runs agno's real search path with no API key. What it cost: any change to chunking, embedder or corpus makes the committed index stale, and the gate fails until someone rebuilds the index and baseline locally with `OPENAI_API_KEY` and commits them.

**(c) Own scorers for retrieval, DeepEval for generation.** recall@k, MRR and nDCG@10 are computed by `scorers.py` over character spans. DeepEval is used only for the generation layer (faithfulness and answer relevancy).

**(d) Two leakage subsets.** The no-leakage subset follows the design spec: no judge rated leakage heavy and the longest copied run is under 5 tokens. The short-copy subset keeps only the copied-run condition, as a robustness view that does not depend on the judges' leakage labels.

## What did not work, and findings

- **5 questions have recall@10 = 0 under production**; 3 of them are recovered by every other config, 2 are not recovered by any config. Source: `results/failures.md`.
  - `r1-clt-041` [procedimento] "Como é calculado o pagamento mensal dos professores com base nas aulas semanais e nas faltas?" CLT Art. 320, passage length 562 characters. Cause not established. Recovered by chunk1500 (rank 1), chunk800 (rank 2), hybrid (rank 1) and rerank (rank 1).
  - `r1-clt-044` [procedimento] "Os municípios podem criar regras que contrariem as normas e instruções federais sobre o funcionamento dessas atividades?" CLT Art. 69, passage length 416 characters. Cause not established. Recovered by chunk1500 (rank 4), chunk800 (rank 1), hybrid (rank 2) and rerank (rank 1).
  - `r1-cpc-000` [procedimento] "Quais são os requisitos para que a eleição de foro tenha validade em um contrato?" CPC Art. 63, passage length 1361 characters. Cause not established. Recovered by chunk1500 (rank 1), chunk800 (rank 1), hybrid (rank 2) and rerank (rank 1).
  - `r1-cpc-016` [conceito] "Quais são as defesas que podem ser apresentadas nesse tipo de processo?" The question has no antecedent for "esse tipo de processo". In the generation run the agent asked for clarification without searching, which `results/generation_pre_adoption.md` counts as the one no-retrieval answer. Not recovered: miss under production, chunk1500, chunk800, hybrid and rerank.
  - `r1-cpc-004` [fato_pontual] "Quando a desistência da ação passa a ter efeito legal?" The golden passage is CPC Art. 200, whose parágrafo único says the desistência takes effect only after judicial homologation. None of the 10 chunks hybrid returns overlaps that passage; 4 of them contain the word "desistência" from other provisions, including CPC Art. 485 and Art. 1.040. Not recovered: miss under production, chunk1500, chunk800, hybrid and rerank.
- **The `cliente_id` filter runs after top-k, and it shows.** agno 2.4.7's `LanceDb.search` asks LanceDB for `limit` rows and nothing else (`agno/vectordb/lancedb/lance_db.py:474-483`), then drops in Python the rows whose `meta_data` does not match the filter (`lance_db.py:486-503`); filter expressions are refused with a warning (`lance_db.py:467-469`). Measured on a two-tenant table built offline from the same corpus and the pre-adoption 5000/0 chunking (tenant 0 owns cdc and clt, 149 chunks; tenant 1 owns cpc and lgpd, 136 chunks; 285 in total), with `limit=10`. The same build under the adopted 1500/150 chunking produces 1054 chunks; `results/multitenant.md` was not rerun, because the filter behaviour it documents is a property of agno's search path, not of the chunk size:
  - Searched for the tenant that owns the question's document, 26 of 59 questions got fewer than 10 rows (12 of 28 for tenant 0, mean 8.54 rows; 14 of 31 for tenant 1, mean 9.19) and none got 0. recall@10 did not move: 0.929 and 0.903, the same as the single-tenant index on the same questions.
  - Searched for the tenant that does not own it, all 59 got fewer than 10 rows and 33 got 0 (17 of 31 for tenant 0, 16 of 28 for tenant 1), although each tenant holds more than 130 chunks.
  - Rows any search returned for the wrong tenant: 0. The filter has not leaked data between tenants in any of the 236 searches (59 questions, both tenants, with and without over-fetching).
  - The harness retriever now over-fetches: `LanceDbRetriever` asks agno for `k * OVERFETCH_FACTOR` rows (factor 10), keeps the first k that survive the filter, and records the shortfall (`last_shortfall`) instead of retrying. With it, the owning tenant got 10 rows on all 59 questions; the non-owning search got 10 rows on all 31 questions for tenant 0, and tenant 1 still came up short on 10 of 28 (mean 8.18). This is a mitigation in the harness, not a fix in the app: `ia/` is unchanged, and over-fetching only lowers the chance of a short result set, since a tenant with very little data can still come up short. It applies to plain vector search only; the hybrid and rerank paths keep their candidate counts, because a longer cut changes their order, and the single-tenant numbers in `results/report.md` are unchanged.
  - A real pre-filter needs `cliente_id` as a column the vector search can filter on. agno's table has only `vector`, `id` and `payload` (`lance_db.py:236-251`), with `cliente_id` inside the `payload` JSON string, so it needs a change in agno or a custom vector store.
  - agno's `Knowledge.insert` catches an embedding error, logs it and inserts 0 chunks for that document (`agno/knowledge/knowledge.py:3899-3905`), so the offline build checks each document's chunk count instead of relying on an exception. Source: `results/multitenant.md`.
- **Hybrid full-text search has no Portuguese stemming.** It runs over the `payload` column with agno's native LanceDB FTS (`use_tantivy=False`). On the no-leakage subset, hybrid lowers recall@1 (0.500 vs 0.650) and MRR (0.667 vs 0.742) against dense chunk1500. Source: `results/notes.md`, sections 5 and 6.
- **The reranker reloads its model on every call.** agno 2.4.7's `SentenceTransformerReranker._rerank` constructs a new `CrossEncoder` per call, so every timed rerank search includes loading `BAAI/bge-reranker-v2-m3` from disk. p50 search is 45356 ms. It was measured as is, not patched. Source: `results/notes.md`, section 7.
- **The same unpatched reranker swallows its own failures, and one published rerank row is plain vector search.** agno 2.4.7's `Reranker.rerank` catches every exception from `_rerank`, logs it and returns the candidates in their incoming distance order (`agno/knowledge/reranker/sentence_transformer.py:49-54`). On the 2026-09-15 run that happened for `r1-cdc-056`, the first of the 59 questions, so its row in the `rerank` tables is plain vector search with nothing in the artifact saying so. No published number moves: that question scores 1.000 on every metric either way, and its 116305.2 ms was the slowest of the 59 latencies the 45356 ms p50 is the median of. Forcing `_rerank` to raise reproduces the 2026-09-15 list exactly, and letting it work reproduces today's. What varies between rebuilds and what does not: rebuilding the 1500/150 index offline from the committed corpus and cache reproduces the committed table bit for bit in either insertion order, including every `_distance`, for all 59 questions at depth 100; a `rerank` run does not reproduce, because the fallback is silent and the harness records nothing that distinguishes it. The trigger of that one failure is not established. Source: `results/rerank_silent_fallback.md`.
- **The agent abstained on 0 of 7 completed out-of-scope runs**, under the pre-adoption config and with no abstention instruction: it answered all of them from general knowledge. **Fixed.** Task 20 added an abstention rule to `JuriAI.INSTRUCTIONS`, and the rerun abstains on 10 of 10. The fix brought its own failure mode, over-refusal in scope, which the two published judge means cannot see; both directions are now measured offline and gated, 10 of 10 out of scope and 1 of 30 in scope. Sources: `results/generation_pre_adoption.md`, `results/generation_adoption.md` and `results/abstention.md`.
- **3 of 10 out-of-scope runs failed on rate limits.** A single agent turn with the pre-adoption retrieval config (5000-character chunks, 10 results per search) requested 39229 to 40571 tokens, above a Tier 1 OpenAI account's 30,000 gpt-4o tokens-per-minute limit. **Measured and gone:** at 1500/150 the largest turn is 6257 input tokens, so no single turn can exhaust the per-minute budget, and the rerun had 0 failed runs. What remains is a harness property, not a chunking one: nothing paces a run, so consecutive turns can still accumulate inside one minute, which is how 4 rows failed on the first pass of that rerun before being retried. Sources: `results/generation_pre_adoption.md` and `results/generation_adoption.md`.
- **Nothing reindexes a document that is already in LanceDB.** Known limitation, not fixed in this task. `usuarios/signals.py:7-16` queues the OCR and indexing chain only under `if created:`, and `ia/tasks.py:44-56` (`rag_documentos`) is the only writer into the `documentos` table, with `usuarios/signals.py:5` as its only caller. There is no management command, admin action or scheduled task that rebuilds it. So after the chunking change the table mixes 5000/0 rows written before the deploy with 1500/150 rows written after it. What limits the damage is that `render.yaml` lines 17 and 18 set `DATA_DIR=/tmp/juri-ai`, ephemeral storage on Render's free plan, so the table is emptied by every deploy, restart or idle spin-down and is refilled only by documents uploaded after that point. Source: `results/adoption.md`.
- **The first CI runs failed before any job started.** The workflow used `${{ runner.temp }}` in job-level `env`, where GitHub does not allow the `runner` context ("Invalid workflow file: Unrecognized named-value: 'runner'"). PR #11 fixed it by moving `DATA_DIR` into the test step's env.
- **pandas was an undeclared dependency.** A clean-venv CI simulation found that agno 2.4.7 `LanceDb` search calls `to_pandas()`, while pandas was installed only through docling, which the CI install excludes. `pandas==2.3.3` is now declared in `requirements.txt`.

## CI regression gate

The workflow [`.github/workflows/groundtruth.yml`](../../.github/workflows/groundtruth.yml) runs on every pull request, on pushes to main, and on manual dispatch. It installs the app dependencies without the OCR stack plus `evals/groundtruth/requirements.txt`, then runs `python -m pytest evals/groundtruth/tests -q -m "not needs_api"`, with no API key. Three tests in [`tests/test_gate.py`](tests/test_gate.py) form the `retrieval-gate` job:

- `test_production_index_matches_current_retrieval_config`: the committed index fingerprint must match the production config, which is 1500/150 since `results/adoption.md`.
- `test_production_recall_at_10_does_not_regress`: the production config runs over the golden set offline, and recall@10 must not drop more than 0.01 below [`baseline.json`](baseline.json) (0.9322033898305084). A stale query cache, a stale index or a changed golden set size also fails the test, with the local rebuild command in the message.
- `test_production_mrr_does_not_regress`: the same offline run, shared with the recall@10 test, and mrr must not drop more than 0.02 below `baseline.json` (0.8107344632768362). The tolerance is wider than recall@10's because a single golden question moving from hit to miss shifts mrr by up to 1/59 (about 0.017); the gate exists to catch real regressions, not that noise. A baseline written before this key existed fails with a message naming the rebuild command, not a `KeyError`.

The baseline was 0.9152542372881356 and 0.5944175410277106 under the 5000/0 chunking. The gate now holds production to the higher numbers.

Three more gate tests in [`tests/test_abstention_gate.py`](tests/test_abstention_gate.py) hold the abstention behaviour in both directions. They run the offline phrasing detector [`generation/refusal.py`](generation/refusal.py) over the committed `generation/answers.jsonl` and compare the two counts with [`generation/abstention_baseline.json`](generation/abstention_baseline.json), which is a separate file from `baseline.json` because the two gates fail for different reasons:

- `test_out_of_scope_abstentions_do_not_regress`: detected abstentions among the 10 out-of-scope rows, baseline 10, and the tolerance is exact, so the count may not fall at all. The agent is expected to abstain when the knowledge base does not cover the question.
- `test_golden_refusals_do_not_rise`: refusals among the 30 golden rows, baseline 1, and the tolerance is exact, so the count may not rise at all. This is the direction the published metrics are blind to: a refusal asserts nothing, so DeepEval scored `r1-cdc-060`'s refusal faithfulness 1.00 and relevancy 1.00 and an over-refusing agent raises both means. The failure message points at `results/abstention.md`.
- `test_the_committed_answers_still_hold_the_run_the_baseline_was_taken_from`: the two sample sizes, 30 and 10, must still match the baseline, so neither count is compared against a different run.

Both tolerances are exact because these are integer counts read from one committed file, not a live run: the same file yields the same integers every time, so there is no measurement noise to absorb, and one row is a large step at this n, 10 percentage points out of 10 rows and 3.3 out of 30. A baseline missing a key fails with the rebuild command in the message, not a `KeyError`.

**What this gate is and is not.** It reads a committed artifact produced by a paid run, so it catches a change to that record, not a change in live behaviour: editing `JuriAI.INSTRUCTIONS` does not fail CI until the generation run is rerun and re-recorded in `generation/answers.jsonl`. It does not protect production behaviour. The detector also matches a small set of known phrasings rather than understanding the answer, so a paraphrased refusal escapes it and both counts are floors: the out-of-scope count can only be too low, and so can the in-scope count, which is the direction that hides over-refusal. The two-judge rubric in `generation/abstention.py` stays the reference for out-of-scope abstention; on this run the detector agrees with it on 10 of 10 rows. `results/abstention.md` has the counts, the agreement and what the metric does not see.

**Demo.** [PR #12](https://github.com/yagosamu/juri_ai/pull/12) deliberately changed `MAX_RESULTS` from 10 to 3. The check failed with 2 failed and 175 passed tests: `test_production_recall_at_10_does_not_regress` with "recall@10 dropped from 0.915 to 0.780 (max drop 0.01)", and `test_production_config::test_constants_match_agno_defaults_documented_in_spec` with "assert 3 == 10". The PR was closed without merge. The same change later also failed `test_production_mrr_does_not_regress` with "mrr dropped from 0.594 to 0.568 (max drop 0.02)". Those quoted numbers are the pre-adoption baseline the gate compared against at the time, and that second test has since been renamed `test_constants_match_the_adopted_production_configuration`.

![CI gate failing on demo PR #12](results/ci_gate_failing.png)

**What the gate does not stop.** A second workflow, [`.github/workflows/groundtruth-baseline-label.yml`](../../.github/workflows/groundtruth-baseline-label.yml), runs the `baseline-change` job on every pull request and again whenever a label is added or removed, and fails when a protected path (`baseline.json`, `golden/golden_set.jsonl`, `indexes/**`, `cache/queries/**`, `generation/answers.jsonl` or `generation/abstention_baseline.json`) changed without the `baseline-change` label, naming the changed files and asking a maintainer to review the numbers before adding the label. So a pull request that edits `baseline.json` together with a regression, changes the golden set and the baseline together, or re-records the generation run the abstention counts are measured from, now fails unless a maintainer adds that label. In a single-maintainer repository this is a speed bump, not an authorization control: the same person proposing the change can also add the label, so it only guarantees a deliberate second look, not review by someone else. On retrieval the gate still checks only the production config's recall@10 and mrr; recall@1, nDCG and the other configs are not gated. On generation it checks only the two abstention counts; faithfulness and relevancy are reported but not gated, and the two counts are read from a committed artifact rather than measured live.

## Observability

![Langfuse trace list](../../screenshots/langfuse-traces.png)

![Langfuse trace detail](../../screenshots/langfuse-trace-detail.png)

Langfuse traces of real JuriAI answers from the Groundtruth run on 2026-09-16. Prompt and completion content is redacted by the production masking hook.

Production tracing (`ia/observability.py`, called by `ensure_agno_tracing()` in `ia/views.py`) was switched on for 3 golden questions: r1-clt-045, r1-cdc-062 and r1-lgpd-071.

- Each agent run appeared as an `Assistente_Jurídico_Virtual.run` trace with an agent span, a small gpt-4o call deciding to search (about 470 input tokens), the `search_knowledge_base` tool span, and a gpt-4o answer call with the retrieved context (11,825 to 14,833 input tokens).
- Latency was 8.55 to 9.14 s per run. Langfuse-computed cost was $0.0343 to $0.0393 per run.
- agno's background memory-update calls appeared as separate `OpenAIChat.invoke` traces of about 900 input tokens, costing $0.0031 to $0.0047 each. Langfuse shows these calls, which `run.metrics` does not meter, so the measured cost in `results/generation_pre_adoption.md` excludes them.
- Every trace and observation input and output shows `[REDACTED]` from the closed-allowlist masking hook.

## Reproduce

Run every command from the repository root. Commands are taken from each module's docstring and argparse definition.

### Install

```bash
pip install -r requirements.txt -r evals/groundtruth/requirements.txt
pip install -r evals/groundtruth/requirements-local.txt   # local only: sentence-transformers, deepeval, anthropic
```

CI installs `requirements.txt` without `docling` and `mpire`, plus `evals/groundtruth/requirements.txt`. DeepEval runs with `DEEPEVAL_TELEMETRY_OPT_OUT=1`, which `generation/scoring.py` sets before importing it.

### Environment variables

- `OPENAI_API_KEY`: embeddings, question generation, gpt-4.1 judge, the agent and DeepEval.
- `ANTHROPIC_API_KEY`: the claude-haiku-4-5 judge.
- Optional, for Langfuse tracing: `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`.

### Commands

"Paid API" marks commands that call OpenAI or Anthropic.

| step | command | paid API |
|---|---|---|
| Corpus: download from Planalto and normalize | `.venv/Scripts/python.exe -m evals.groundtruth.corpus.build_corpus` | no |
| Corpus: normalize from `corpus/raw` without downloading | `.venv/Scripts/python.exe -m evals.groundtruth.corpus.build_corpus --from-raw` | no |
| Index: production (committed; rebuild only after a config or corpus change) | `.venv/Scripts/python.exe -m evals.groundtruth.indexer --config production` | yes, embeddings |
| Index: comparison configs (production, chunk1500, hybrid and rerank all reuse one index) | `.venv/Scripts/python.exe -m evals.groundtruth.indexer --config chunk1500` and `--config chunk800` | yes, embeddings |
| Retrieval run from the committed query cache | `.venv/Scripts/python.exe -m evals.groundtruth.run_retrieval --config production chunk1500 chunk800 hybrid rerank --offline` | no |
| Retrieval run and new baseline | `.venv/Scripts/python.exe -m evals.groundtruth.run_retrieval --config production --write-baseline` | only on a query cache miss |
| Report | `.venv/Scripts/python.exe -m evals.groundtruth.report` | no |
| Gate and offline tests | `.venv/Scripts/python.exe -m pytest evals/groundtruth/tests -q -m "not needs_api"` | no |
| Golden set: candidates | `.venv/Scripts/python.exe -m evals.groundtruth.golden.candidates --round 1` | yes, gpt-4.1-mini |
| Golden set: triage | `.venv/Scripts/python.exe -m evals.groundtruth.golden.triage` (`--smoke`, `--limit N`, `--force`) | yes, gpt-4.1 and text-embedding-3-large |
| Golden set: recompute triage flags from stored verdicts | `.venv/Scripts/python.exe -m evals.groundtruth.golden.triage --rederive-flags` | no |
| Golden set: judges | `.venv/Scripts/python.exe -m evals.groundtruth.golden.judges` (`--smoke`, `--limit N`) | yes, gpt-4.1 and claude-haiku-4-5 |
| Golden set: consensus | `.venv/Scripts/python.exe -m evals.groundtruth.golden.consensus` | no |
| Out-of-scope check | `.venv/Scripts/python.exe -m evals.groundtruth.generation.out_of_scope_check` | yes, text-embedding-3-large, gpt-4.1 and claude-haiku-4-5 |
| Generation: smoke run, one question of each kind, written only under `runtime/generation` | `.venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation --smoke --limit-golden 1 --limit-oos 1` | yes |
| Generation: full run | `.venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation` | yes, gpt-4o, gpt-4.1-mini, gpt-4.1 and claude-haiku-4-5 |
| Generation: re-render `results/generation.md` from the verdicts already in `generation/scores.json` | `.venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation --report-only` | no |
| Generation: score the answers already in `generation/answers.jsonl`, then re-render | `.venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation --score-only` | yes, gpt-4.1-mini, gpt-4.1 and claude-haiku-4-5 |
| Generation: rerun failed runs only | `.venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation --only oos-01 oos-07 oos-08` | yes |
| Generation: recount the two abstention numbers from the committed answers | `.venv/Scripts/python.exe -m evals.groundtruth.generation.refusal` | no |

Notes:
- Since the adoption, `production` and `chunk1500` have the same parameters and the same index name, `c1500_o150_text-embedding-3-small_d1536`, so `--config production` and `--config chunk1500` build and read the same table. The 5000/0 table stays committed because `results/report.md` and the multi-tenant work still refer to it.
- The indexer's `--offline` flag fails on an embedding cache miss instead of calling the API. `cache/chunks` is not committed, so a rebuild from a clean clone calls the embeddings API.
- The rerank config downloads `BAAI/bge-reranker-v2-m3` from Hugging Face on first use.
- `--only` refuses any id that is not currently a failed run.
- A generation run fills the runtime `documentos` table only when it is empty, then requires exactly the chunk count the current `ia/retrieval_config.py` produces over the corpus (1054 at 1500/150, 285 at the pre-adoption 5000/0). After a chunking change, delete `runtime/generation/lancedb/documentos.lance` first, or the run stops on that count before it spends anything.
- `--report-only` makes no call, but it only re-renders verdicts that are already in `generation/scores.json`. It computes no score, and it refuses to run when a stored verdict carries no `answer_sha256` to match against the answers on disk, so it can never publish one run's verdicts as another run's result. Scoring answers that have no stored verdicts is `--score-only`, which calls the three judge models and costs money. Neither one calls the agent, so neither can change an answer or spend agent tokens.
- `golden/candidates.jsonl`, `golden/triage.jsonl`, `golden/judgments.jsonl` and `golden/golden_set.jsonl` are committed, so triage, judges and consensus can be rerun from a clone against the published candidates. Regenerating candidates calls gpt-4.1-mini at temperature 0.7, so new candidates would differ from the published set.
- `generation/answers.jsonl` and `generation/scores.json` were gitignored until Task 21 and are now committed, because the abstention gate reads the answers and the `baseline-change` label job can only protect a tracked path. The files were committed unchanged: re-rendering `results/generation.md` from them produces the committed file byte for byte.

## Disclosure

- The benchmark measures the published pipeline over a public corpus, not the law office's traffic.
- The golden set has no human legal review. It was selected by consensus of two LLM judges, gpt-4.1 and claude-haiku-4-5.
- The 59-question set is below the design target of 100.
- The generation layer uses a sample of 30 golden questions drawn with seed 7, and both of its scorers are LLM judges.
- The generation harness paces nothing: `generate_answers` calls the agent back to back with no delay and no backoff, so a run walks into the account's tokens-per-minute window on its own. That is why turns of about 5500 tokens still hit a 30,000 per minute limit, and it means the failed-run count of any generation run is a property of that pacing and of the account tier, not of the chunking being measured. No pacing was added.
- Measured costs are listed in `results/notes.md` (ingestion) and `results/generation.md` (generation).
