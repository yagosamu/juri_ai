import pytest
from agno.knowledge.embedder.base import Embedder

from evals.groundtruth.embedder_cache import (
    CachedEmbedder,
    DegenerateEmbedding,
    EmbeddingCacheCorrupt,
    EmbeddingCacheMiss,
)


class FakeEmbedder(Embedder):
    def __init__(self):
        self.calls = 0

    def get_embedding(self, text):
        self.calls += 1
        return [float(len(text))] * 4


def test_miss_calls_inner_once_and_hit_reads_from_disk(tmp_path):
    inner = FakeEmbedder()
    emb = CachedEmbedder(cache_dir=tmp_path, inner=inner, id="fake", dimensions=4)
    assert emb.get_embedding("abc") == [3.0] * 4
    assert emb.get_embedding("abc") == [3.0] * 4
    assert inner.calls == 1
    emb.save()
    offline = CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    assert offline.get_embedding("abc") == [3.0] * 4
    vec, usage = offline.get_embedding_and_usage("abc")
    assert vec == [3.0] * 4 and usage is None


def test_offline_miss_raises(tmp_path):
    offline = CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    with pytest.raises(EmbeddingCacheMiss):
        offline.get_embedding("never seen")


def test_key_includes_model_id(tmp_path):
    a = CachedEmbedder(cache_dir=tmp_path, inner=FakeEmbedder(), id="m1", dimensions=4)
    a.get_embedding("x")
    a.save()
    b = CachedEmbedder(cache_dir=tmp_path, inner=None, id="m2", dimensions=4)
    with pytest.raises(EmbeddingCacheMiss):
        b.get_embedding("x")


class EmptyEmbedder(Embedder):
    """Mimics OpenAIEmbedder with a bad key: logs the API error and returns an empty list."""

    def __init__(self):
        self.calls = 0

    def get_embedding(self, text):
        self.calls += 1
        return []


class ShortEmbedder(Embedder):
    """Returns a well-formed vector of the wrong dimension."""

    def __init__(self):
        self.calls = 0

    def get_embedding(self, text):
        self.calls += 1
        return [0.5, 0.5]


def test_empty_embedding_raises_and_is_not_cached(tmp_path):
    inner = EmptyEmbedder()
    emb = CachedEmbedder(cache_dir=tmp_path, inner=inner, id="fake", dimensions=4)
    with pytest.raises(DegenerateEmbedding) as excinfo:
        emb.get_embedding("some chunk text")
    assert inner.calls == 1
    message = str(excinfo.value)
    assert "fake" in message and "4" in message and "some chunk text" in message
    emb.save()
    assert not (tmp_path / "keys.json").exists()
    assert not (tmp_path / "vectors.npy").exists()


def test_wrong_dimension_embedding_raises_and_is_not_cached(tmp_path):
    inner = ShortEmbedder()
    emb = CachedEmbedder(cache_dir=tmp_path, inner=inner, id="fake", dimensions=4)
    with pytest.raises(DegenerateEmbedding):
        emb.get_embedding("some chunk text")
    with pytest.raises(DegenerateEmbedding):
        emb.get_embedding_and_usage("some chunk text")
    emb.save()
    assert not (tmp_path / "keys.json").exists()
    assert not (tmp_path / "vectors.npy").exists()


def test_offline_miss_still_raises_cache_miss_not_degenerate(tmp_path):
    """The offline path is unchanged: a miss with inner=None is EmbeddingCacheMiss."""
    offline = CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    with pytest.raises(EmbeddingCacheMiss):
        offline.get_embedding("never seen")


class DimEmbedder(Embedder):
    """Returns a well-formed vector whose length is the dimension it was built for."""

    def __init__(self, dims):
        self.dims = dims
        self.calls = 0

    def get_embedding(self, text):
        self.calls += 1
        return [float(self.dims)] * self.dims


def test_key_includes_dimensions(tmp_path):
    """text-embedding-3-small supports dimension reduction, so the same id at a different
    dimension is a different embedder and must not reuse cached vectors."""
    a = CachedEmbedder(cache_dir=tmp_path, inner=DimEmbedder(4), id="m1", dimensions=4)
    a.get_embedding("x")
    a.save()
    offline = CachedEmbedder(cache_dir=tmp_path, inner=None, id="m1", dimensions=2)
    with pytest.raises(EmbeddingCacheMiss):
        offline.get_embedding("x")
    inner = DimEmbedder(2)
    online = CachedEmbedder(cache_dir=tmp_path, inner=inner, id="m1", dimensions=2)
    assert online.get_embedding("x") == [2.0, 2.0]
    assert inner.calls == 1


def test_cache_hit_of_wrong_length_is_rejected(tmp_path):
    """A stale or corrupted cached vector must not be handed out unvalidated."""
    emb = CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    emb._vectors[emb._key("poisoned")] = [1.0, 2.0]  # simulates a corrupted cache file
    with pytest.raises(DegenerateEmbedding):
        emb.get_embedding("poisoned")


def _write_cache(cache_dir, keys, rows):
    import json as _json

    import numpy as _np
    cache_dir.mkdir(parents=True, exist_ok=True)
    _np.save(cache_dir / "vectors.npy", _np.asarray(rows, dtype=_np.float32))
    (cache_dir / "keys.json").write_text(_json.dumps(keys), encoding="utf-8")


def test_cache_load_rejects_half_written_pair(tmp_path):
    _write_cache(tmp_path, ["a"], [[1.0, 2.0, 3.0, 4.0]])
    (tmp_path / "vectors.npy").unlink()
    with pytest.raises(EmbeddingCacheCorrupt) as excinfo:
        CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    assert str(tmp_path) in str(excinfo.value)


def test_cache_load_rejects_vectors_without_keys(tmp_path):
    _write_cache(tmp_path, ["a"], [[1.0, 2.0, 3.0, 4.0]])
    (tmp_path / "keys.json").unlink()
    with pytest.raises(EmbeddingCacheCorrupt) as excinfo:
        CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    assert str(tmp_path) in str(excinfo.value)


def test_cache_load_rejects_duplicate_keys(tmp_path):
    _write_cache(tmp_path, ["a", "a"], [[1.0] * 4, [2.0] * 4])
    with pytest.raises(EmbeddingCacheCorrupt):
        CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)


def test_cache_load_rejects_key_and_vector_count_mismatch(tmp_path):
    _write_cache(tmp_path, ["a"], [[1.0] * 4, [2.0] * 4])
    with pytest.raises(EmbeddingCacheCorrupt):
        CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)


def test_cache_load_accepts_a_consistent_pair(tmp_path):
    _write_cache(tmp_path, ["a", "b"], [[1.0] * 4, [2.0] * 4])
    emb = CachedEmbedder(cache_dir=tmp_path, inner=None, id="fake", dimensions=4)
    assert len(emb._vectors) == 2
