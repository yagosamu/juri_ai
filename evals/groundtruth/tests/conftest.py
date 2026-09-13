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
