# Multitenant cliente_id post-filter measurement (Task 18)

## Setup

- 2 tenants: tenant 0 owns cdc and clt, tenant 1 owns cpc and lgpd.
- 1 LanceDB table, 285 chunks total (tenant 0: 149, tenant 1: 136), the same total as the single-tenant production index.
- Same production chunking as ia/retrieval_config.py: chunk_size=5000, chunk_overlap=0, embedder text-embedding-3-small at 1536 dimensions, search limit 10.
- No API call: chunk embeddings came from the local cache/chunks and query embeddings from the committed cache/queries, both with online=False and OPENAI_API_KEY empty.

## Rows returned after the cliente_id filter

Before: the production call, limit=10 asked of agno, then the cliente_id filter. After: the harness retriever's over-fetch rule applied to this table, limit=100 (OVERFETCH_FACTOR=10) asked of agno, then the filter, keeping the first 10 survivors. Owning tenant only; the non-owning tenant is in the cross-tenant check below.

| tenant | questions | mean rows before | <10 before | 0 before | mean rows after | <10 after | 0 after |
|---|---|---|---|---|---|---|---|
| 0 | 28 | 8.54 | 12 | 0 | 10.00 | 0 | 0 |
| 1 | 31 | 9.19 | 14 | 0 | 10.00 | 0 | 0 |

## recall@10 and mrr per tenant, against the single-tenant baseline

Single-tenant production baseline (results/report.md, over all 59 questions): recall@10 = 0.915, mrr = 0.594. The single-tenant columns below are the same production index and retriever restricted to each tenant's questions.

| tenant | questions | single-tenant recall@10 | single-tenant mrr | recall@10 before | mrr before | recall@10 after | mrr after |
|---|---|---|---|---|---|---|---|
| 0 | 28 | 0.929 | 0.550 | 0.929 | 0.588 | 0.929 | 0.588 |
| 1 | 31 | 0.903 | 0.635 | 0.903 | 0.651 | 0.903 | 0.651 |

## Cross-tenant check

Each question was also searched with the cliente_id of the tenant that does not own its document. That tenant gets rows back from its own documents, which is legitimate; the rows from the owning tenant's documents must be 0.

| run | searched tenant | questions | mean rows returned | fewer than 10 rows | 0 rows | rows from the owning tenant's documents |
|---|---|---|---|---|---|---|
| without over-fetch | 0 | 31 | 0.81 | 31 | 17 | 0 |
| without over-fetch | 1 | 28 | 1.46 | 28 | 16 | 0 |
| with over-fetch | 0 | 31 | 10.00 | 0 | 0 | 0 |
| with over-fetch | 1 | 28 | 8.18 | 10 | 0 | 0 |

Rows any query returned for the wrong tenant, over both searches of every question: 0 before over-fetching, 0 after. Both must be 0: a query for tenant A must never return a chunk belonging to tenant B, since a leak here is a data isolation bug and not a recall problem.

## What this means for production

With a table holding many clients, the top 10 rows are drawn before the filter, so a client with few documents can receive fewer than 10 chunks, or none.
