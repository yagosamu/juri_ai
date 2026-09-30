# Chunking adoption: 1500/150 in production

## What changed

`CHUNK_SIZE` 5000 to 1500 and `CHUNK_OVERLAP` 0 to 150 in `ia/retrieval_config.py`.

Nothing else in that module changed: the embedder (`text-embedding-3-small`, 1536 dimensions), the
search type (`vector`), the distance (`cosine`), `MAX_RESULTS` (10) and the reranker (none) are as
they were. `evals/groundtruth/config.py` derives `PRODUCTION` from that module, so `production` and
`chunk1500` now have the same parameters and resolve to the same index name,
`c1500_o150_text-embedding-3-small_d1536`. Both entries are kept: `results/report.md`,
`results/significance.md` and `results/failures.md` refer to the configuration as `chunk1500`, and
the two names share one table on disk.

## Before and after, 59 golden questions

Before is the `production` row and after is the `chunk1500` row of `results/report.md`, the Task 7
comparison that motivated this change. In that report `production` means the 5000/0 configuration,
the one in place before this adoption.

| metric | before (5000/0) | after (1500/150) |
|---|---|---|
| recall@1 | 0.373 | 0.712 |
| recall@5 | 0.864 | 0.932 |
| recall@10 | 0.915 | 0.932 |
| mrr | 0.594 | 0.811 |
| ndcg@10 | 0.675 | 0.842 |
| p50 search ms | 12 | 14 |

p50 search ms is wall-clock time inside `retriever.search` with the query embedding already
computed, on the machine that ran it. It is informational and not gated.

## Significance of each gap

Quoted from the "Comparisons, full (n=59)" table of `results/significance.md`, rows
`chunk1500 vs production`. Seed 20260917, 10000 bootstrap resamples, 10000 sign-flip permutations,
alpha 0.05, Holm correction over the 5 pre-registered pairs per metric.

| metric | first (chunk1500) | second (production) | b, c or difference interval | raw p | Holm p | significant at alpha 0.05 |
|---|---|---|---|---|---|---|
| recall@1 | 0.712 | 0.373 | b=23, c=3 | 0.0001 | 0.0004 | yes |
| recall@10 | 0.932 | 0.915 | b=3, c=2 | 1.0000 | 1.0000 | no |
| mrr | 0.811 | 0.594 | diff=0.216 [0.119, 0.314] | 0.0002 | 0.0010 | yes |

The recall@10 gain, 0.915 to 0.932, is not significant: b=3, c=2, raw p 1.0000, Holm p 1.0000. The
case for this change rests on recall@1 and mrr, the two metrics that describe the first answer.

`results/significance.md` covers recall@1, recall@10 and mrr only, its pre-registered `METRICS`
constant. The recall@5, ndcg@10 and p50 gaps in the table above were not part of that analysis, so
no significance is claimed for them.

## New baseline

`baseline.json`, rewritten by
`.venv/Scripts/python.exe -m evals.groundtruth.run_retrieval --config production --offline --write-baseline`:

```json
{
  "config": "production",
  "n_golden": 59,
  "recall@10": 0.9322033898305084,
  "mrr": 0.8107344632768362,
  "index_fingerprint": {
    "chunk_size": 1500,
    "chunk_overlap": 150,
    "embedder_id": "text-embedding-3-small",
    "embedder_dimensions": 1536
  }
}
```

The previous payload was recall@10 0.9152542372881356 and mrr 0.5944175410277106, with
`chunk_size` 5000 and `chunk_overlap` 0.

The three `gate` tests in `tests/test_gate.py` compare against this file, not the old one:
`test_production_index_matches_current_retrieval_config` requires the committed index fingerprint to
be 1500/150, `test_production_recall_at_10_does_not_regress` allows at most a 0.01 drop below
0.9322033898305084, and `test_production_mrr_does_not_regress` allows at most a 0.02 drop below
0.8107344632768362. The gate therefore holds production to the higher numbers from now on.

The committed index was rebuilt offline from the local chunk embedding cache, with no API call. The
5000/0 table stays committed because `results/report.md` and the multi-tenant work still run
configurations that read it.

## Cost

From `results/notes.md`, section 4. Embedding tokens counted with tiktoken `cl100k_base` over the
chunk texts, at $0.02 per 1M tokens.

| configuration | n_chunks | ingestion tokens | ingestion cost |
|---|---|---|---|
| before (5000/0) | 285 | 434515 | $0.00869 |
| after (1500/150) | 1054 | 483330 | $0.00967 |

The index grows from 285 to 1054 chunks and ingestion rises from 434515 to 483330 tokens, $0.00869
to $0.00967 for the 4 statutes of this corpus.

## What this change does not measure

The generation quality of the new chunking. `results/generation_pre_adoption.md` scored the agent's
answers under the old 5000/0 retrieval configuration; rerunning generation under 1500/150 is Task 20
and is not part of this record.

## Transfer caveat

The comparison ran on 4 public Brazilian statutes, while production documents are petitions and
contracts passed through OCR. The gain is measured on this corpus only, and nothing here shows that
it carries over to OCR output.

## How production reindexes existing documents

It does not. There is no code path that reindexes an already indexed `Documentos` row.

- `usuarios/signals.py:7-16`: the `post_save` receiver on `Documentos` builds the django-q `Chain`
  only under `if created:` (line 12). It appends `ocr_and_markdown_file` and then `rag_documentos`
  (lines 14 and 15) and runs the chain. On any later save of the same row, `created` is false and
  nothing is queued.
- `ia/tasks.py:44-56`: `rag_documentos` is the only writer into the `documentos` LanceDB table. It
  calls `JuriAI.knowledge.insert` with `build_document_reader()`. That reader reads `CHUNK_SIZE` and
  `CHUNK_OVERLAP` from `ia.retrieval_config` at call time (`ia/tasks.py:26-41`), so it picks up
  1500/150 with no further change, but only for documents inserted after this deploy.
- `rag_documentos` has no other caller: `usuarios/signals.py:5` is its only import in the repository.
  There is no management command, no admin action and no scheduled task that rebuilds the table. The
  only other code that touches it is `usuarios/views.py:900-915`, in `excluir_conta`, which deletes
  rows by `cliente_id` when a user deletes the account.
- Consequence: after this change the `documentos` table holds 5000/0 rows for every document indexed
  before the deploy and 1500/150 rows for every document indexed after it, in one table searched by
  one query. No migration is written in this task.

`render.yaml` lines 17 and 18 set `DATA_DIR=/tmp/juri-ai`. `core/settings.py:197` derives
`LANCEDB_URI` from `DATA_DIR`, and `core/settings.py:179` puts `MEDIA_ROOT` there too. On Render's
free plan `/tmp` is ephemeral container storage, so the LanceDB index and the uploaded files do not
survive a deploy, a restart or the free plan's idle spin-down. That limits the mixed-chunking
problem above: the index is short lived, and each restart begins with an empty table. It also means
the index is rebuilt only by whatever documents are uploaded after that restart, since nothing
reindexes the rows already in Postgres.

One further observed fact about the deployed service: `render.yaml` declares a single `web` service
whose `startCommand` is `bash start.sh`, which runs gunicorn only (`start.sh:11`). `Q_CLUSTER` in
`core/settings.py` uses the ORM broker, so `Chain.run()` writes the task to the database, but no
`qcluster` worker process is declared in `render.yaml` to consume it.
