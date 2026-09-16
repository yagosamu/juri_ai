"""R2 memory isolation: each question starts with a fresh, empty agno memory sqlite file.

Prevents one question's memory from leaking into the next, which would make answers depend on
the order questions run in.
"""
from pathlib import Path


def fresh_memory_path(runtime_dir, question_id: str) -> Path:
    """A distinct <runtime_dir>/memory/<question_id>.sqlite3 path, with any existing file removed first."""
    path = Path(runtime_dir) / "memory" / f"{question_id}.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return path
