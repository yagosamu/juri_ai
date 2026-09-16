"""R2 runtime guard: refuse to touch the agent's stores outside evals/groundtruth/runtime/generation.

Mandatory before any insert or agent run. Prevents a run from writing into the repository's real
lancedb/ directory or db.sqlite3.
"""
from pathlib import Path


class RuntimeGuardError(RuntimeError):
    pass


def assert_runtime_uri(uri, runtime_dir) -> None:
    """Raise RuntimeGuardError unless uri resolves to a path inside runtime_dir."""
    resolved = Path(str(uri)).resolve()
    base = Path(runtime_dir).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise RuntimeGuardError(
            f"refusing to touch a store outside the runtime dir: {resolved} is not inside {base}") from None
