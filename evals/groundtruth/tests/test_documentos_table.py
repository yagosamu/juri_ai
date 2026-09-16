import pytest

from evals.groundtruth.generation.documentos_table import TableCountError, ensure_documentos_table


class FakeVectorDb:
    """counts: the get_count() return value on each successive call (last value repeats)."""

    def __init__(self, counts):
        self.counts = list(counts)
        self.calls = 0

    def get_count(self):
        value = self.counts[min(self.calls, len(self.counts) - 1)]
        self.calls += 1
        return value


class FakeKnowledge:
    def __init__(self, counts):
        self.vector_db = FakeVectorDb(counts)
        self.inserted = []

    def insert(self, **kwargs):
        self.inserted.append(kwargs)


def test_ensure_documentos_table_inserts_once_when_empty():
    knowledge = FakeKnowledge([0, 285])
    corpus = {"cdc": "texto cdc", "clt": "texto clt"}
    count = ensure_documentos_table(knowledge, corpus, reader="fake-reader", expected_count=285)
    assert count == 285
    assert len(knowledge.inserted) == 2
    assert {c["name"] for c in knowledge.inserted} == {"cdc", "clt"}
    assert all(c["metadata"]["cliente_id"] == 0 for c in knowledge.inserted)
    assert all(c["reader"] == "fake-reader" for c in knowledge.inserted)


def test_ensure_documentos_table_skips_insert_when_already_populated():
    knowledge = FakeKnowledge([285])
    count = ensure_documentos_table(knowledge, {"cdc": "x"}, reader="fake-reader", expected_count=285)
    assert count == 285
    assert knowledge.inserted == []


def test_ensure_documentos_table_raises_on_wrong_count_after_insert():
    knowledge = FakeKnowledge([0, 100])
    with pytest.raises(TableCountError):
        ensure_documentos_table(knowledge, {"cdc": "x"}, reader="fake-reader", expected_count=285)


def test_ensure_documentos_table_raises_on_wrong_count_when_already_populated():
    knowledge = FakeKnowledge([9])
    with pytest.raises(TableCountError):
        ensure_documentos_table(knowledge, {"cdc": "x"}, reader="fake-reader", expected_count=285)
    assert knowledge.inserted == []


def test_ensure_documentos_table_uses_custom_tenant():
    knowledge = FakeKnowledge([0, 1])
    ensure_documentos_table(knowledge, {"cdc": "x"}, reader="fake-reader", tenant=99, expected_count=1)
    assert knowledge.inserted[0]["metadata"]["cliente_id"] == 99
