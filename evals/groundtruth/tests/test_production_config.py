from evals.groundtruth.config import CONFIGS, PRODUCTION
from ia import retrieval_config as cfg


def test_constants_match_the_adopted_production_configuration():
    assert cfg.EMBEDDER_ID == "text-embedding-3-small"
    assert cfg.EMBEDDER_DIMENSIONS == 1536
    assert cfg.CHUNK_SIZE == 1500
    assert cfg.CHUNK_OVERLAP == 150
    assert cfg.SEARCH_TYPE == "vector"
    assert cfg.DISTANCE == "cosine"
    assert cfg.MAX_RESULTS == 10
    assert cfg.RERANKER is None


def test_production_and_chunk1500_are_both_kept_and_share_one_index():
    """Task 19 adopted chunk1500 as production, so the two entries describe the same table.

    chunk1500 stays under its own name because results/report.md, results/significance.md and
    results/failures.md refer to it that way.
    """
    assert "chunk1500" in CONFIGS
    assert CONFIGS["production"] is PRODUCTION
    chunk1500 = CONFIGS["chunk1500"]
    assert PRODUCTION.index_name == chunk1500.index_name
    assert PRODUCTION.fingerprint() == chunk1500.fingerprint()


def test_juriai_agent_uses_retrieval_config(django_ready):
    from agno.vectordb.distance import Distance
    from agno.vectordb.search import SearchType

    from ia.agents import JuriAI

    vector_db = JuriAI.knowledge.vector_db
    assert vector_db.search_type == SearchType(cfg.SEARCH_TYPE)
    assert vector_db.distance == Distance(cfg.DISTANCE)
    assert vector_db.embedder.id == cfg.EMBEDDER_ID
    assert vector_db.embedder.dimensions == cfg.EMBEDDER_DIMENSIONS
    assert vector_db.reranker is None
    assert JuriAI.knowledge.max_results == cfg.MAX_RESULTS


def test_rag_documentos_reader_uses_retrieval_config(django_ready):
    from agno.knowledge.chunking.fixed import FixedSizeChunking

    from ia.tasks import build_document_reader

    reader = build_document_reader()
    assert isinstance(reader.chunking_strategy, FixedSizeChunking)
    assert reader.chunking_strategy.chunk_size == cfg.CHUNK_SIZE
    assert reader.chunking_strategy.overlap == cfg.CHUNK_OVERLAP
