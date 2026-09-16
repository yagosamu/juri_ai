"""R3: insert the corpus into the runtime documentos table exactly once, the same Knowledge.insert
path production uses (agno.knowledge.knowledge.Knowledge.insert -> reader -> LanceDb.insert).
"""


class TableCountError(RuntimeError):
    pass


def ensure_documentos_table(knowledge, corpus: dict, reader, tenant: int = 0, expected_count: int = 285) -> int:
    """Insert every corpus document only when the runtime table is empty; then require expected_count chunks."""
    count = knowledge.vector_db.get_count()
    if count == 0:
        for doc_id, text in corpus.items():
            knowledge.insert(name=doc_id, text_content=text, metadata={"cliente_id": tenant, "name": doc_id},
                             reader=reader)
        count = knowledge.vector_db.get_count()
    if count != expected_count:
        raise TableCountError(f"documentos table has {count} chunks, expected {expected_count}")
    return count
