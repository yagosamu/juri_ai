import re

from evals.groundtruth.config import CONFIGS, PRODUCTION
from ia import retrieval_config as cfg

# The phrase the abstention rubric (generation/abstention.py RUBRIC) looks for in an answer before it
# will label the run "abstained". Kept as one constant so the test below fails if either side moves.
RUBRIC_NO_BASIS_PHRASE = "não encontrou base nos documentos"


def _flat(text: str) -> str:
    """Instruction text with runs of whitespace collapsed, so a reflow cannot fail these assertions."""
    return re.sub(r"\s+", " ", text).strip().lower()


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


def test_the_abstention_rubric_still_looks_for_the_phrase_the_instruction_targets():
    """Binds the two sides: if the rubric stops asking for "no basis in the documents", the
    instruction written against it has to be rewritten too."""
    from evals.groundtruth.generation.abstention import RUBRIC

    assert RUBRIC_NO_BASIS_PHRASE in _flat(RUBRIC)


def test_juriai_instructions_carry_the_abstention_rule(django_ready):
    """Task 20 ruling 1: search first, then say plainly that the documents do not cover it instead of
    answering from general knowledge. The wording has to satisfy generation/abstention.py's rubric."""
    from ia.agents import JuriAI

    text = _flat(JuriAI.INSTRUCTIONS)
    assert "busque na base de conhecimento" in text
    assert RUBRIC_NO_BASIS_PHRASE in text
    assert "não responda com conhecimento geral" in text


def test_the_abstention_rule_spares_datajud_and_keeps_the_unsure_guidance(django_ready):
    from ia.agents import JuriAI

    text = _flat(JuriAI.INSTRUCTIONS)
    assert "datajud" in text
    assert "se não tiver certeza sobre alguma informação, indique isso ao usuário" in text


def test_build_agent_passes_the_instructions_to_the_agent(django_ready):
    from ia.agents import JuriAI

    agent = JuriAI.build_agent(knowledge_filters={"cliente_id": 0})
    assert agent.instructions == JuriAI.INSTRUCTIONS


def test_rag_documentos_reader_uses_retrieval_config(django_ready):
    from agno.knowledge.chunking.fixed import FixedSizeChunking

    from ia.tasks import build_document_reader

    reader = build_document_reader()
    assert isinstance(reader.chunking_strategy, FixedSizeChunking)
    assert reader.chunking_strategy.chunk_size == cfg.CHUNK_SIZE
    assert reader.chunking_strategy.overlap == cfg.CHUNK_OVERLAP
