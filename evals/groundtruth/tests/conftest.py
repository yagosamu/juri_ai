import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "needs_api: calls a paid API; skipped in CI")
    config.addinivalue_line("markers", "gate: CI regression gate")


@pytest.fixture(scope="session")
def django_ready():
    """Configure Django without a database so ia.agents can be imported."""
    tmp = tempfile.mkdtemp(prefix="groundtruth_django_")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ.setdefault("SECRET_KEY", "test-only")
    os.environ.setdefault("DATA_DIR", tmp)
    os.environ.setdefault("LANCEDB_URI", str(Path(tmp) / "lancedb"))
    os.environ.setdefault("AGNO_MEMORY_DB_FILE", str(Path(tmp) / "agno_memory.sqlite3"))
    os.environ.setdefault("OPENAI_API_KEY", "offline")
    import django

    django.setup()
    return True


# The Task 7 comparison ran with production at 5000/0. Task 19 adopted 1500/150, so re-running
# `run_retrieval --config production` now overwrites the gitignored results/production.json with
# post-adoption numbers, and the reports built from it no longer match the committed
# results/significance.md and results/failures.md, which are the record of that comparison.
PRE_ADOPTION_CHUNKING = {"chunk_size": 5000, "chunk_overlap": 0}


def pre_adoption_mismatch(results_dir) -> str | None:
    """The skip reason when results/production.json holds a run of a different chunking, else None."""
    import json

    path = results_dir / "production.json"
    if not path.exists():
        return None
    config = json.loads(path.read_text(encoding="utf-8")).get("config", {})
    found = {key: config.get(key) for key in PRE_ADOPTION_CHUNKING}
    if found == PRE_ADOPTION_CHUNKING:
        return None
    return (f"results/production.json holds a {found} run, and the committed report records the "
            f"pre-adoption {PRE_ADOPTION_CHUNKING} comparison (see results/adoption.md). Restore "
            "the pre-adoption results/*.json to reproduce it.")
