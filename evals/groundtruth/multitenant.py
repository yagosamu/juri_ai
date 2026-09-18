# evals/groundtruth/multitenant.py
"""Task 18: build a two-tenant LanceDB index offline, and measure how agno's cliente_id post-filter
(evals/groundtruth/retriever.py, agno's lance_db.py:474-503) behaves across tenants on the corpus we
already have. No API call: chunk embeddings come from the local cache/chunks (gitignored) and query
embeddings from the committed cache/queries, both with online=False.

Split, fixed and stated here so the measurement is reproducible: tenant 0 owns cdc and clt, tenant 1
owns cpc and lgpd. The table lives under evals/groundtruth/runtime/multitenant/lancedb, which is
gitignored and never committed; only results/multitenant.md is.

Usage: .venv/Scripts/python.exe -m evals.groundtruth.multitenant
"""
import sys
from pathlib import Path
from typing import Optional

from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.embedder.base import Embedder
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.text_reader import TextReader
from agno.vectordb.distance import Distance
from agno.vectordb.lancedb import LanceDb
from agno.vectordb.search import SearchType

from evals.groundtruth import retriever as retriever_mod
from evals.groundtruth.config import (CACHE_DIR, GOLDEN_SET, GROUNDTRUTH_DIR, INDEXES_DIR, PRODUCTION, RESULTS_DIR,
                                      load_corpus)
from evals.groundtruth.embedder_cache import openai_embedder
from evals.groundtruth.golden.schema import GoldenItem, load_golden
from evals.groundtruth.indexer import rebuild_command
from evals.groundtruth.retriever import build_retriever, chunk_offsets
from evals.groundtruth.scorers import Span, score_item

TENANT_DOCS: dict[int, tuple[str, ...]] = {0: ("cdc", "clt"), 1: ("cpc", "lgpd")}
DOC_TENANT: dict[str, int] = {doc_id: tenant for tenant, docs in TENANT_DOCS.items() for doc_id in docs}

MULTITENANT_RUNTIME_DIR = GROUNDTRUTH_DIR / "runtime" / "multitenant" / "lancedb"
EXPECTED_CHUNKS = 285  # same total as the single-tenant production index (indexes/c5000_o0_*.json)
MULTITENANT_REPORT = RESULTS_DIR / "multitenant.md"
SEARCH_LIMIT = PRODUCTION.max_results  # 10, the same limit production's Knowledge.search asks for


def _refuse_protected(runtime_dir: Path) -> None:
    """Refuse to build into the committed indexes or the embedding caches. The table name is the
    production index name, so building into INDEXES_DIR would drop and overwrite the production
    table; that happened once, on 2026-09-17. Read INDEXES_DIR and CACHE_DIR at call time."""
    target = Path(runtime_dir).resolve()
    for protected in (INDEXES_DIR, CACHE_DIR):
        root = Path(protected).resolve()
        if target == root or root in target.parents:
            raise ValueError(
                f"refusing to build the multitenant table in {runtime_dir}: it is under {protected}, "
                f"which must stay byte-identical. Build under {MULTITENANT_RUNTIME_DIR} instead.")


def build_multitenant_index(corpus: dict[str, str], embedder: Embedder,
                            runtime_dir: Path = MULTITENANT_RUNTIME_DIR,
                            expected_chunks: int = EXPECTED_CHUNKS) -> dict[int, int]:
    """Insert every corpus document through the same Knowledge.insert path indexer.build_index uses
    (TextReader + FixedSizeChunking with the production chunk_size and chunk_overlap from
    ia/retrieval_config.py, via config.PRODUCTION), tagged with its tenant's cliente_id instead of
    indexer.py's single production tenant. One table, two tenants.

    Returns {tenant: n_chunks}. Raises ValueError when a document ends up with a chunk count other
    than the one the chunker produces for it, or when the table does not hold exactly
    expected_chunks chunks in total. The per-document check matters because agno's Knowledge.insert
    catches an embedding error (such as EmbeddingCacheMiss from the offline embedder), logs it and
    inserts 0 chunks for that document instead of raising.
    """
    _refuse_protected(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    vector_db = LanceDb(uri=str(runtime_dir), table_name=PRODUCTION.index_name, embedder=embedder,
                        search_type=SearchType.vector, distance=Distance(PRODUCTION.distance), use_tantivy=False)
    if vector_db.exists():
        vector_db.drop()
    knowledge = Knowledge(vector_db=vector_db, max_results=PRODUCTION.max_results)
    reader = TextReader(chunking_strategy=FixedSizeChunking(chunk_size=PRODUCTION.chunk_size,
                                                             overlap=PRODUCTION.chunk_overlap))
    rebuild = (f"If the chunk embedding cache is missing entries, refill cache/chunks with an online build: "
               f"{rebuild_command(PRODUCTION)}")
    counts = {tenant: 0 for tenant in TENANT_DOCS}
    for doc_id, text in corpus.items():
        if doc_id not in DOC_TENANT:
            raise ValueError(f"document {doc_id!r} is not assigned to a tenant in TENANT_DOCS: {TENANT_DOCS}")
        tenant = DOC_TENANT[doc_id]
        before = vector_db.get_count()
        knowledge.insert(name=doc_id, text_content=text, metadata={"cliente_id": tenant, "name": doc_id}, reader=reader)
        inserted = vector_db.get_count() - before
        expected_doc = len(chunk_offsets(text, PRODUCTION.chunk_size, PRODUCTION.chunk_overlap))
        if inserted != expected_doc:
            raise ValueError(
                f"document {doc_id!r} inserted {inserted} chunks but the chunker produces {expected_doc}; "
                f"agno's Knowledge.insert swallows embedding errors, so a cache miss shows up only here. {rebuild}")
        counts[tenant] += inserted
    total = sum(counts.values())
    if total != expected_chunks:
        raise ValueError(
            f"multitenant index holds {total} chunks across tenants {counts}, expected {expected_chunks} "
            f"(the same total as the production index); the corpus or chunking changed. {rebuild}")
    return counts


def open_multitenant_table(embedder: Embedder, runtime_dir: Path = MULTITENANT_RUNTIME_DIR) -> LanceDb:
    """Reopen the table build_multitenant_index wrote, the same way agno's LanceDb reopens a table."""
    return LanceDb(uri=str(runtime_dir), table_name=PRODUCTION.index_name, embedder=embedder,
                   search_type=SearchType.vector, distance=Distance(PRODUCTION.distance), use_tantivy=False)


def search_tenant(vector_db, offsets: dict[str, dict[int, tuple[int, int]]], query: str, tenant: int,
                  limit: int) -> list[Span]:
    """The same call agno's LanceDb.search makes in production and in
    evals.groundtruth.retriever.LanceDbRetriever.search: vector_search(query, limit) first, then a
    Python filter on cliente_id (agno's lance_db.py:474-503). Maps each surviving row back to the
    [start, end) span the retriever computes, using the same chunk_offsets function."""
    docs = vector_db.search(query, limit=limit, filters={"cliente_id": tenant})
    spans = []
    for doc in docs:
        doc_id, chunk = doc.meta_data.get("name"), doc.meta_data.get("chunk")
        start, end = offsets[doc_id][chunk]
        spans.append(Span(doc_id, start, end))
    return spans


def measure(golden: list[GoldenItem], corpus: dict[str, str], embedder: Embedder,
           runtime_dir: Path = MULTITENANT_RUNTIME_DIR, overfetch_factor: int = 1,
           search_limit: int = SEARCH_LIMIT) -> tuple[list[dict], int]:
    """For every golden question, run the search twice, the way production does
    (filters={"cliente_id": t}, requesting search_limit * overfetch_factor rows before the filter and
    keeping at most search_limit survivors, like LanceDbRetriever.search):

    - for the tenant that owns the question's document: rows_after_filter, and recall@10 and MRR
      from the existing scorers;
    - for the tenant that does not own it: other_tenant_rows, the rows it gets back (from its own
      documents, which is legitimate), and owner_rows_in_other_tenant, the rows among them that come
      from the owning tenant's documents, where the correct answer is 0.

    cross_tenant_rows counts, over both searches of every question, the rows whose document truly
    belongs to a tenant other than the one the search was filtered by (DOC_TENANT disagrees with the
    filter). It must be 0: a leak here is a data isolation bug in the filter or in how the index was
    tagged, not a recall problem.

    Returns (per-question rows, cross_tenant_rows).
    """
    vector_db = open_multitenant_table(embedder, runtime_dir)
    offsets = {doc_id: chunk_offsets(text, PRODUCTION.chunk_size, PRODUCTION.chunk_overlap)
              for doc_id, text in corpus.items()}
    requested = search_limit * overfetch_factor
    rows: list[dict] = []
    cross_tenant_rows = 0
    for item in golden:
        doc_id = item.passages[0].doc_id
        owner = DOC_TENANT[doc_id]
        other = next(t for t in TENANT_DOCS if t != owner)
        owner_spans = search_tenant(vector_db, offsets, item.question, owner, requested)[:search_limit]
        other_spans = search_tenant(vector_db, offsets, item.question, other, requested)[:search_limit]
        cross_tenant_rows += sum(1 for s in owner_spans if DOC_TENANT.get(s.doc_id) != owner)
        cross_tenant_rows += sum(1 for s in other_spans if DOC_TENANT.get(s.doc_id) != other)
        passages = [Span(p.doc_id, p.start, p.end) for p in item.passages]
        rows.append({"id": item.id, "category": item.category, "tenant": owner,
                     "rows_after_filter": len(owner_spans), "other_tenant": other,
                     "other_tenant_rows": len(other_spans),
                     "owner_rows_in_other_tenant": sum(1 for s in other_spans if DOC_TENANT.get(s.doc_id) == owner),
                     **score_item(owner_spans, passages)})
    return rows, cross_tenant_rows


def tenant_stats(rows: list[dict], search_limit: int = SEARCH_LIMIT) -> dict[int, dict]:
    """Per tenant: question count, mean rows_after_filter, how many questions got fewer than
    search_limit rows, how many got 0, and mean recall@10 and mrr."""
    out = {}
    for tenant in sorted(TENANT_DOCS):
        trows = [r for r in rows if r["tenant"] == tenant]
        n = len(trows)
        out[tenant] = {
            "n": n,
            "mean_rows": sum(r["rows_after_filter"] for r in trows) / n,
            "under_limit": sum(1 for r in trows if r["rows_after_filter"] < search_limit),
            "zero": sum(1 for r in trows if r["rows_after_filter"] == 0),
            "recall@10": sum(r["recall@10"] for r in trows) / n,
            "mrr": sum(r["mrr"] for r in trows) / n,
        }
    return out


def single_tenant_rows(golden: list[GoldenItem], corpus: dict[str, str], embedder: Embedder) -> list[dict]:
    """The single-tenant production numbers, per question, so each tenant can be compared with the
    same questions on the production index: LanceDbRetriever over the committed production index,
    read only, tagged with the tenant that would own each question here."""
    retriever = build_retriever(PRODUCTION, corpus, embedder)
    rows = []
    for item in golden:
        hits = retriever.search(item.question, k=SEARCH_LIMIT)
        retrieved = [Span(h.doc_id, h.start, h.end) for h in hits]
        passages = [Span(p.doc_id, p.start, p.end) for p in item.passages]
        rows.append({"id": item.id, "tenant": DOC_TENANT[item.passages[0].doc_id],
                     "rows_after_filter": len(retrieved), **score_item(retrieved, passages)})
    return rows


def render_report(counts: dict[int, int], before_rows: list[dict], before_cross: int,
                  after_rows: Optional[list[dict]], after_cross: Optional[int],
                  single_rows: Optional[list[dict]] = None, overfetch_factor: Optional[int] = None) -> str:
    total = sum(counts.values())
    before_stats = tenant_stats(before_rows)
    after_stats = tenant_stats(after_rows) if after_rows is not None else None
    single_stats = tenant_stats(single_rows) if single_rows is not None else None

    lines = ["# Multitenant cliente_id post-filter measurement (Task 18)", "", "## Setup", "",
             "- 2 tenants: tenant 0 owns cdc and clt, tenant 1 owns cpc and lgpd.",
             f"- 1 LanceDB table, {total} chunks total (tenant 0: {counts[0]}, tenant 1: {counts[1]}), "
             "the same total as the single-tenant production index.",
             f"- Same production chunking as ia/retrieval_config.py: chunk_size={PRODUCTION.chunk_size}, "
             f"chunk_overlap={PRODUCTION.chunk_overlap}, embedder {PRODUCTION.embedder_id} at "
             f"{PRODUCTION.embedder_dimensions} dimensions, search limit {SEARCH_LIMIT}.",
             "- No API call: chunk embeddings came from the local cache/chunks and query embeddings from "
             "the committed cache/queries, both with online=False and OPENAI_API_KEY empty.", ""]

    lines += ["## Rows returned after the cliente_id filter", ""]
    if after_stats is None:
        lines += ["Over-fetching (Ruling 3) has not landed yet; this is the current post-filter "
                  "behaviour, limit=10, no over-fetch.", "",
                  "| tenant | questions | mean rows | fewer than 10 rows | 0 rows |",
                  "|---|---|---|---|---|"]
        for t in sorted(TENANT_DOCS):
            s = before_stats[t]
            lines.append(f"| {t} | {s['n']} | {s['mean_rows']:.2f} | {s['under_limit']} | {s['zero']} |")
    else:
        lines += [f"Before: the production call, limit={SEARCH_LIMIT} asked of agno, then the cliente_id "
                  f"filter. After: the harness retriever's over-fetch rule applied to this table, limit={SEARCH_LIMIT * (overfetch_factor or 0)} "
                  f"(OVERFETCH_FACTOR={overfetch_factor}) asked of agno, then the filter, keeping the first "
                  f"{SEARCH_LIMIT} survivors. Owning tenant only; the non-owning tenant is in the "
                  "cross-tenant check below.", "",
                  "| tenant | questions | mean rows before | <10 before | 0 before | "
                  "mean rows after | <10 after | 0 after |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in sorted(TENANT_DOCS):
            b, a = before_stats[t], after_stats[t]
            lines.append(f"| {t} | {b['n']} | {b['mean_rows']:.2f} | {b['under_limit']} | {b['zero']} | "
                         f"{a['mean_rows']:.2f} | {a['under_limit']} | {a['zero']} |")

    lines += ["", "## recall@10 and mrr per tenant, against the single-tenant baseline", "",
             "Single-tenant production baseline (results/report.md, over all 59 questions): "
             "recall@10 = 0.915, mrr = 0.594. The single-tenant columns below are the same production "
             "index and retriever restricted to each tenant's questions.", ""]
    head = ["tenant", "questions"]
    if single_stats is not None:
        head += ["single-tenant recall@10", "single-tenant mrr"]
    head += ["recall@10 before", "mrr before"] if after_stats is not None else ["recall@10", "mrr"]
    if after_stats is not None:
        head += ["recall@10 after", "mrr after"]
    lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for t in sorted(TENANT_DOCS):
        b = before_stats[t]
        cells = [str(t), str(b["n"])]
        if single_stats is not None:
            cells += [f"{single_stats[t]['recall@10']:.3f}", f"{single_stats[t]['mrr']:.3f}"]
        cells += [f"{b['recall@10']:.3f}", f"{b['mrr']:.3f}"]
        if after_stats is not None:
            cells += [f"{after_stats[t]['recall@10']:.3f}", f"{after_stats[t]['mrr']:.3f}"]
        lines.append("| " + " | ".join(cells) + " |")

    lines += ["", "## Cross-tenant check", "",
              "Each question was also searched with the cliente_id of the tenant that does not own its "
              "document. That tenant gets rows back from its own documents, which is legitimate; the rows "
              "from the owning tenant's documents must be 0.", "",
              "| run | searched tenant | questions | mean rows returned | fewer than 10 rows | 0 rows | "
              "rows from the owning tenant's documents |",
              "|---|---|---|---|---|---|---|"]
    runs = [("without over-fetch", before_rows)] + ([("with over-fetch", after_rows)] if after_rows is not None else [])
    for label, run_rows in runs:
        for t in sorted(TENANT_DOCS):
            orows = [r for r in run_rows if r["other_tenant"] == t]
            lines.append(f"| {label} | {t} | {len(orows)} | "
                         f"{sum(r['other_tenant_rows'] for r in orows) / len(orows):.2f} | "
                         f"{sum(1 for r in orows if r['other_tenant_rows'] < SEARCH_LIMIT)} | "
                         f"{sum(1 for r in orows if r['other_tenant_rows'] == 0)} | "
                         f"{sum(r['owner_rows_in_other_tenant'] for r in orows)} |")
    lines.append("")
    if after_cross is None:
        lines.append(f"Rows any query returned for the wrong tenant, over both searches of every question: "
                     f"{before_cross}. This must be 0: a query for tenant A must never return a chunk "
                     "belonging to tenant B, since a leak here is a data isolation bug and not a recall problem.")
    else:
        lines.append(f"Rows any query returned for the wrong tenant, over both searches of every question: "
                     f"{before_cross} before over-fetching, {after_cross} after. Both must be 0: a query for "
                     "tenant A must never return a chunk belonging to tenant B, since a leak here is a data "
                     "isolation bug and not a recall problem.")

    lines += ["", "## What this means for production", "",
             "With a table holding many clients, the top 10 rows are drawn before the filter, so a "
             "client with few documents can receive fewer than 10 chunks, or none.", ""]
    return "\n".join(lines)


def _run(overfetch_after: bool) -> str:
    corpus = load_corpus()
    golden = load_golden(GOLDEN_SET)
    chunk_embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions,
                                     CACHE_DIR / "chunks", online=False)
    # online=False embedders never write: CachedEmbedder.save() is a no-op unless a new vector was
    # fetched, which cannot happen offline, so there is no save() here and cache/ stays untouched.
    counts = build_multitenant_index(corpus, chunk_embedder, runtime_dir=MULTITENANT_RUNTIME_DIR)

    query_embedder = openai_embedder(PRODUCTION.embedder_id, PRODUCTION.embedder_dimensions,
                                     CACHE_DIR / "queries", online=False)
    before_rows, before_cross = measure(golden, corpus, query_embedder, runtime_dir=MULTITENANT_RUNTIME_DIR,
                                        overfetch_factor=1)
    after_rows = after_cross = None
    if overfetch_after and hasattr(retriever_mod, "OVERFETCH_FACTOR"):
        after_rows, after_cross = measure(golden, corpus, query_embedder, runtime_dir=MULTITENANT_RUNTIME_DIR,
                                          overfetch_factor=retriever_mod.OVERFETCH_FACTOR)
    single_rows = single_tenant_rows(golden, corpus, query_embedder)

    text = render_report(counts, before_rows, before_cross, after_rows, after_cross, single_rows,
                         overfetch_factor=getattr(retriever_mod, "OVERFETCH_FACTOR", None))
    MULTITENANT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    MULTITENANT_REPORT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv()
    print(_run(overfetch_after=True))
