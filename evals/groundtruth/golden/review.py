"""Human review loop. a=accept, e=edit question, c=change category, r=reject, q=quit (progress is saved).
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.review --reviewer yago
"""
import argparse
import datetime as dt
import json
import sys
import textwrap
from typing import Callable

from evals.groundtruth.config import CANDIDATES, DECISIONS, GOLDEN_SET, load_corpus
from evals.groundtruth.golden.schema import GoldenItem, Passage, load_golden, save_golden

CATEGORIES = ["fato_pontual", "conceito", "procedimento"]


def already_decided() -> set[str]:
    if not DECISIONS.exists():
        return set()
    return {json.loads(l)["candidate_id"] for l in DECISIONS.read_text(encoding="utf-8").splitlines() if l.strip()}


def load_candidates() -> list[dict]:
    """Read candidates.jsonl, keeping only the first line seen for each candidate_id.

    A rerun of candidates.py for the same round (or any other source of a duplicated id) must
    never let the same candidate be shown to the reviewer twice in one session.
    """
    seen: dict[str, dict] = {}
    for line in CANDIDATES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cand = json.loads(line)
        seen.setdefault(cand["candidate_id"], cand)
    return list(seen.values())


# validate_candidate deliberately checks only doc_id and the span, never the category. A bad span
# means the data is corrupt (the article metadata cannot be trusted) so the candidate is refused
# outright and never shown. A bad category is just a mislabeled-but-possibly-good question, and the
# reviewer can supply a correct one, so it is handled by re-prompting in main() instead of refusing:
# refusing it would throw away a candidate a human could still accept.
def validate_candidate(cand: dict, corpus: dict[str, str]) -> str | None:
    """Return an error message if the candidate's span cannot be trusted, else None.

    doc_id must be a real corpus document and the interval must satisfy
    0 <= start < end <= len(document); Python slicing accepts out-of-bounds intervals silently,
    so this check is the only thing standing between a bad candidate and a silently wrong passage.
    """
    doc_id = cand.get("doc_id")
    if doc_id not in corpus:
        return f"unknown doc_id {doc_id!r}"
    start, end = cand.get("start"), cand.get("end")
    doc_len = len(corpus[doc_id])
    if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= doc_len):
        return f"span [{start!r}:{end!r}) invalid for {doc_id!r} (document length {doc_len})"
    return None


def prompt_category(input_fn: Callable[[str], str], current: str) -> str:
    """Prompt for a category, re-prompting until the answer is blank (keep current) or valid."""
    while True:
        raw = input_fn(f"category {CATEGORIES} > ").strip()
        if not raw:
            return current
        if raw in CATEGORIES:
            return raw
        print(f"unknown category {raw!r}; choose one of {CATEGORIES} or leave blank to keep {current!r}")


def require_valid_category(input_fn: Callable[[str], str], category: str) -> str:
    """Force a valid category, with no blank-input fallback because `category` may not be one.

    Used right before an accept when the candidate's stored category is not one of CATEGORIES
    (typically a hand-edited or legacy candidates file, since candidates.py now types the field).
    Unlike prompt_category, blank input is not accepted here: there is no valid current value to
    fall back to, and GoldenItem would raise on an invalid category anyway.
    """
    while category not in CATEGORIES:
        print(f"category {category!r} is not valid; choose one of {CATEGORIES} to accept this candidate")
        category = input_fn(f"category {CATEGORIES} > ").strip()
    return category


def decide(input_fn: Callable[[str], str], question: str, category: str) -> tuple[str, str, str]:
    """Run the accept, edit, category, reject, quit loop; return (key, question, category)."""
    while True:
        key = input_fn("[a]ccept [e]dit [c]ategory [r]eject [q]uit > ").strip().lower()
        if key == "e":
            question = input_fn("new question > ").strip() or question
        elif key == "c":
            category = prompt_category(input_fn, category)
        elif key == "a":
            if category not in CATEGORIES:
                category = require_valid_category(input_fn, category)
            return key, question, category
        elif key in ("r", "q"):
            return key, question, category
        else:
            print(f"unknown command {key!r}; use a, e, c, r or q")


def main(reviewer: str, input_fn: Callable[[str], str] = input) -> None:
    corpus = load_corpus()
    golden = load_golden(GOLDEN_SET) if GOLDEN_SET.exists() else []
    done = already_decided()
    pending = [c for c in load_candidates() if c["candidate_id"] not in done]
    print(f"{len(golden)} golden items so far, {len(pending)} candidates pending")
    for cand in pending:
        if cand["candidate_id"] in done:
            continue  # decided earlier in this same run; never present a duplicate twice
        error = validate_candidate(cand, corpus)
        if error:
            print(f"\nrefusing [{cand['candidate_id']}]: {error}")
            continue
        passage = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
        print("\n" + "=" * 80)
        print(f"[{cand['candidate_id']}] {cand['doc_id'].upper()} {cand['header']}  ({cand['category']})")
        print(textwrap.fill(passage[:1200], width=100))
        print(f"\nQ: {cand['question']}")
        question, category = cand["question"], cand["category"]
        if category not in CATEGORIES:
            print(f"warning: stored category {category!r} is not valid; choose one of {CATEGORIES} to accept")
        key, question, category = decide(input_fn, question, category)
        if key == "q":
            return
        if key == "a":
            golden.append(GoldenItem(
                id=cand["candidate_id"], question=question, category=category,
                passages=[Passage(doc_id=cand["doc_id"], start=cand["start"], end=cand["end"])],
                source_article=f"{cand['doc_id']} {cand['header']}",
                reviewed_by=reviewer, reviewed_at=dt.date.today().isoformat(),
                review_mode="human_full",
            ))
            save_golden(golden, GOLDEN_SET)
        with DECISIONS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"candidate_id": cand["candidate_id"], "decision": key}) + "\n")
        done.add(cand["candidate_id"])
    print(f"done: {len(golden)} golden items")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer", required=True)
    main(parser.parse_args().reviewer)
