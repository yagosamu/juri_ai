from ia import retrieval_config as cfg


def test_constants_match_agno_defaults_documented_in_spec():
    assert cfg.EMBEDDER_ID == "text-embedding-3-small"
    assert cfg.EMBEDDER_DIMENSIONS == 1536
    assert cfg.CHUNK_SIZE == 5000
    assert cfg.CHUNK_OVERLAP == 0
    assert cfg.SEARCH_TYPE == "vector"
    assert cfg.DISTANCE == "cosine"
    assert cfg.MAX_RESULTS == 10
    assert cfg.RERANKER is None


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
