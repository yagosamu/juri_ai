"""Crash-tolerant reading and appending for JSONL files written one row at a time.

A crash mid-write leaves a partial final line. Readers ignore it with a warning and writers cut it before
appending, so an interrupted run resumes cleanly. A malformed line anywhere else is real corruption and raises.
"""
import json
import sys
from pathlib import Path


def read_jsonl_rows(path: Path) -> list[dict]:
    """Every row of a JSONL file, in file order. A malformed last line is ignored with a warning.

    A crash mid-write leaves a partial final line; ignoring it lets the run resume and write that row
    again. A malformed line anywhere else is real corruption and raises. Lines are decoded one at a time so a
    multi-byte character cut in half by the crash cannot make the whole file unreadable.
    """
    if not path.exists():
        return []
    lines = [(number, raw) for number, raw in enumerate(path.read_bytes().split(b"\n"), start=1) if raw.strip()]
    rows = []
    for position, (number, raw) in enumerate(lines):
        try:
            rows.append(json.loads(raw.decode("utf-8")))
        except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are both ValueError
            if position < len(lines) - 1:
                raise ValueError(f"{path}: line {number} is malformed and is not the last line, "
                                 f"so the file is corrupt: {exc}") from exc
            print(f"WARNING: {path}: ignoring malformed last line {number}, likely left by an interrupted run: "
                  f"{raw[:80]!r}", file=sys.stderr)
    return rows


def drop_malformed_tail(path: Path) -> None:
    """Make the file safe to append to: cut a malformed last line, and end a well-formed one with a newline."""
    if not path.exists():
        return
    data = path.read_bytes()
    body = data.rstrip()
    if not body:
        return
    cut = body.rfind(b"\n") + 1
    try:
        json.loads(body[cut:].decode("utf-8"))
    except ValueError:
        print(f"WARNING: {path}: removing malformed last line before appending: {body[cut:cut + 80]!r}",
              file=sys.stderr)
        with path.open("r+b") as f:
            f.truncate(cut)
        return
    if not data.endswith(b"\n"):
        with path.open("a", encoding="utf-8") as f:
            f.write("\n")
