"""Retrieval configuration used by the JuriAI RAG agent.

The embedder, search type, distance, max results and reranker were implicit Agno defaults
before 2026-09. They are explicit so that evals/groundtruth can measure exactly what
production runs and fail CI when a change regresses recall. Keep this module free of
Django imports.
"""

EMBEDDER_ID = "text-embedding-3-small"
EMBEDDER_DIMENSIONS = 1536

# FixedSizeChunking in characters, split on whitespace. These two values are not Agno's
# TextReader defaults (5000/0) any more: they were chosen by the measured comparison in
# evals/groundtruth/results/report.md and evals/groundtruth/results/significance.md, where
# 1500/150 raised recall@1 from 0.373 to 0.712 and mrr from 0.594 to 0.811 over the 59
# golden questions, both significant after Holm correction. See results/adoption.md.
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150

# agno.vectordb.search.SearchType value: "vector" | "keyword" | "hybrid"
SEARCH_TYPE = "vector"
# agno.vectordb.distance.Distance value: "cosine" | "l2" | "max_inner_product"
DISTANCE = "cosine"

# Knowledge.max_results: documents returned to the agent per search
MAX_RESULTS = 10

# None or "bge-reranker-v2-m3" (see evals/groundtruth/retriever.py)
RERANKER = None
