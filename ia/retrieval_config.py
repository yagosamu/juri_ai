"""Retrieval configuration used by the JuriAI RAG agent.

Every value here was an implicit Agno default before 2026-09. They are explicit so
that evals/groundtruth can measure exactly what production runs and fail CI when
a change regresses recall. Keep this module free of Django imports.
"""

EMBEDDER_ID = "text-embedding-3-small"
EMBEDDER_DIMENSIONS = 1536

# FixedSizeChunking in characters, split on whitespace. Agno's TextReader default.
CHUNK_SIZE = 5000
CHUNK_OVERLAP = 0

# agno.vectordb.search.SearchType value: "vector" | "keyword" | "hybrid"
SEARCH_TYPE = "vector"
# agno.vectordb.distance.Distance value: "cosine" | "l2" | "max_inner_product"
DISTANCE = "cosine"

# Knowledge.max_results: documents returned to the agent per search
MAX_RESULTS = 10

# None or "bge-reranker-v2-m3" (see evals/groundtruth/retriever.py)
RERANKER = None
