"""Embedder wrapper that memoizes vectors on disk so retrieval evals run without API calls.
Layout: <cache_dir>/keys.json (list of sha256 over id, dimensions and text) + <cache_dir>/vectors.npy
(float32, N x dims). Both files must be present together, with unique keys and one row per key."""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from agno.knowledge.embedder.base import Embedder


class EmbeddingCacheMiss(RuntimeError):
    pass


class DegenerateEmbedding(RuntimeError):
    """The inner embedder returned something that is not a usable vector."""


class EmbeddingCacheCorrupt(RuntimeError):
    """The two cache files on disk disagree with each other."""


@dataclass
class CachedEmbedder(Embedder):
    cache_dir: Path = Path(".")
    inner: Optional[Embedder] = None
    id: str = "text-embedding-3-small"
    dimensions: Optional[int] = 1536
    _vectors: Dict[str, List[float]] = field(default_factory=dict, init=False, repr=False)
    _dirty: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        keys_path, vec_path = self.cache_dir / "keys.json", self.cache_dir / "vectors.npy"
        if not keys_path.exists() and not vec_path.exists():
            return
        if not (keys_path.exists() and vec_path.exists()):
            present, missing = (keys_path, vec_path) if keys_path.exists() else (vec_path, keys_path)
            raise self._corrupt(f"{present.name} exists but {missing.name} does not")
        keys = json.loads(keys_path.read_text(encoding="utf-8"))
        vectors = np.load(vec_path)
        if len(set(keys)) != len(keys):
            raise self._corrupt(f"keys.json lists {len(keys) - len(set(keys))} duplicate key(s)")
        if vectors.ndim != 2 or len(keys) != vectors.shape[0]:
            raise self._corrupt(f"keys.json lists {len(keys)} keys but vectors.npy has shape {vectors.shape}")
        self._vectors = {k: vectors[i].tolist() for i, k in enumerate(keys)}

    def _corrupt(self, problem: str) -> EmbeddingCacheCorrupt:
        return EmbeddingCacheCorrupt(
            f"Embedding cache in {self.cache_dir} is corrupt: {problem}. "
            "Delete that directory and rebuild it, or restore both files from the same commit.")

    def _key(self, text: str) -> str:
        """The dimension is part of the key: text-embedding-3-small supports dimension reduction, so the
        same model id at two dimensions returns different vectors for the same text."""
        return hashlib.sha256(f"{self.id}\x00{self.dimensions}\x00{text}".encode("utf-8")).hexdigest()

    def get_embedding(self, text: str) -> List[float]:
        key = self._key(text)
        if key in self._vectors:
            return self._checked(self._vectors[key], text, cached=True)
        if self.inner is None:
            raise EmbeddingCacheMiss(
                f"No cached embedding for text starting {text[:60]!r}. "
                "Rebuild locally with OPENAI_API_KEY and commit the cache.")
        vector = self._checked(self.inner.get_embedding(text), text, cached=False)
        self._vectors[key] = vector
        self._dirty = True
        return vector

    def _checked(self, vector, text: str, *, cached: bool) -> List[float]:
        """Reject a degenerate vector, whether fresh from the inner embedder or read back from the cache.

        A failed embedding call is otherwise indistinguishable from a successful one: OpenAIEmbedder
        logs the API error and returns an empty list, which would be memoized and indexed as a
        plausible-looking row, producing an index with the expected chunk count and meaningless vectors.
        Cache hits are checked as well, so a vector of the wrong length on disk is never handed out.
        """
        problem = None
        if not isinstance(vector, list):
            problem = f"a {type(vector).__name__}"
        elif self.dimensions is not None and len(vector) != self.dimensions:
            problem = f"a list of {len(vector)} values"
        elif not vector:
            problem = "an empty list"
        elif not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in vector):
            problem = "a list containing non-numeric values"
        if problem is not None:
            if cached:
                source, hint = "the cache held", (
                    f"The entry in {self.cache_dir} is stale or damaged; delete that directory and rebuild it.")
            else:
                source, hint = "returned", "Check OPENAI_API_KEY and rate limits; nothing was written to the cache."
            raise DegenerateEmbedding(
                f"Embedder {self.id!r} was expected to return a list of {self.dimensions} floats "
                f"but {source} {problem}, for text starting {text[:60]!r}. {hint}")
        return vector

    def get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        return self.get_embedding(text), None

    def save(self) -> None:
        if not self._dirty:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        keys = list(self._vectors)
        np.save(self.cache_dir / "vectors.npy", np.asarray([self._vectors[k] for k in keys], dtype=np.float32))
        (self.cache_dir / "keys.json").write_text(json.dumps(keys), encoding="utf-8")
        self._dirty = False


def openai_embedder(embedder_id: str, dimensions: int, cache_dir: Path, online: bool) -> CachedEmbedder:
    """Factory: online=True wraps the real OpenAIEmbedder; online=False is cache-only."""
    inner = None
    if online:
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        inner = OpenAIEmbedder(id=embedder_id, dimensions=dimensions)
    return CachedEmbedder(cache_dir=cache_dir, inner=inner, id=embedder_id, dimensions=dimensions)
