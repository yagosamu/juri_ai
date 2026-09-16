from types import SimpleNamespace

import pytest

from evals.groundtruth.generation.guard import RuntimeGuardError, assert_runtime_uri


def test_assert_runtime_uri_passes_when_inside(tmp_path):
    runtime = tmp_path / "runtime" / "generation"
    uri = runtime / "lancedb"
    assert_runtime_uri(str(uri), runtime)  # must not raise


def test_assert_runtime_uri_raises_when_outside(tmp_path):
    runtime = tmp_path / "runtime" / "generation"
    outside = tmp_path / "lancedb"
    with pytest.raises(RuntimeGuardError):
        assert_runtime_uri(str(outside), runtime)


def test_assert_runtime_uri_raises_for_a_relative_repo_root_style_path(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime" / "generation"
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeGuardError):
        assert_runtime_uri("lancedb", runtime)  # relative path resolves against cwd, not runtime


def test_assert_runtime_uri_accepts_a_fake_knowledge_object(tmp_path):
    runtime = tmp_path / "runtime" / "generation"
    knowledge = SimpleNamespace(vector_db=SimpleNamespace(uri=str(runtime / "lancedb")))
    assert_runtime_uri(knowledge.vector_db.uri, runtime)  # must not raise


def test_assert_runtime_uri_rejects_a_sibling_directory_with_a_similar_prefix(tmp_path):
    runtime = tmp_path / "runtime" / "generation"
    sibling = tmp_path / "runtime" / "generation-evil" / "lancedb"
    with pytest.raises(RuntimeGuardError):
        assert_runtime_uri(str(sibling), runtime)
