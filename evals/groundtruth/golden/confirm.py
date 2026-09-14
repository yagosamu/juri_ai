"""Human confirmation of triaged golden-set candidates.

calibrate: a seeded random sample shown blind, with no stored category, no judge verdict and no
flags, so the human fills the judge's rubric independently and agreement can be measured honestly.
flagged and unflagged: the remaining candidates, with the judge's verdict and flag reasons visible.
Every finished item is appended to human_labels.jsonl immediately.
The blind sample must be finished before the other modes open, so judge verdicts cannot anchor it.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.confirm --mode calibrate --reviewer yago
"""
import argparse
import datetime as dt
import json
import random
import sys
import textwrap
from pathlib import Path
from typing import Callable

from evals.groundtruth.config import CALIBRATION_SAMPLE, HUMAN_LABELS, TRIAGE, load_corpus
from evals.groundtruth.golden.jsonl_io import drop_malformed_tail, read_jsonl_rows
from evals.groundtruth.golden.review import CATEGORIES, decide, load_candidates, validate_candidate
from evals.groundtruth.golden.triage import PREVIEW_CHARS, load_triage

CALIBRATION_N = 20
CALIBRATION_SEED = 20260914
ANSWERABLE = {"y": "yes", "p": "partial", "n": "no"}
LEAKAGE = {"n": "none", "s": "some", "h": "heavy"}
CATEGORY_CHOICES = {"f": "fato_pontual", "c": "conceito", "p": "procedimento", **{c: c for c in CATEGORIES}}


def choose_calibration_sample(triage: dict[str, dict], n: int = CALIBRATION_N,
                              seed: int = CALIBRATION_SEED) -> list[str]:
    eligible = sorted(cid for cid, row in triage.items() if row["status"] != "refused")
    return sorted(random.Random(seed).sample(eligible, min(n, len(eligible))))


def load_labels(path: Path) -> dict[str, dict]:
    """Human labels by candidate_id, keeping the first row per id. A truncated last line is ignored."""
    labels: dict[str, dict] = {}
    for row in read_jsonl_rows(path):
        labels.setdefault(row["candidate_id"], row)
    return labels


def calibration_problems(sample_ids: list[str], triage: dict[str, dict], labels: dict[str, dict]) -> list[str]:
    """One line per non-refused sample id that has no label, or whose label mode is not calibrate."""
    problems = []
    for cid in sample_ids:
        if triage[cid]["status"] == "refused":
            continue
        if cid not in labels:
            problems.append(f"{cid}: not labelled yet")
        elif labels[cid].get("mode") != "calibrate":
            problems.append(f"{cid}: label mode is {labels[cid].get('mode')!r}, expected 'calibrate'")
    return problems


def calibration_complete(sample_ids: list[str], triage: dict[str, dict], labels: dict[str, dict]) -> bool:
    """True only when every non-refused sample id has a label written in calibrate mode."""
    return not calibration_problems(sample_ids, triage, labels)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    drop_malformed_tail(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _choice(input_fn: Callable[[str], str], prompt: str, options: dict[str, str]) -> str:
    while True:
        raw = input_fn(prompt).strip().lower()
        if raw in options:
            return options[raw]
        print(f"unknown answer {raw!r}; use one of {sorted(options)}")


def _competitor_labels(input_fn: Callable[[str], str], allowed: set[str]) -> list[str]:
    while True:
        raw = input_fn(f"also answered by {sorted(allowed)}, comma separated, blank for none > ").strip()
        chosen = [x.strip().upper() for x in raw.split(",") if x.strip()]
        unknown = sorted(set(chosen) - allowed)
        if not unknown:
            return chosen
        print(f"unknown competitor labels {unknown}")


def _show(cand: dict, row: dict, corpus: dict[str, str], blind: bool) -> None:
    article = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
    print("\n" + "=" * 80)
    title = f"[{cand['candidate_id']}] {cand['doc_id'].upper()} {cand['header']}"
    print(title if blind else f"{title}  stored category: {cand['category']}")
    print(textwrap.fill(article[:1200], width=100))
    print(f"\nQ: {cand['question']}")
    for c in row.get("competitors", []):
        preview = corpus[c["doc_id"]][c["start"]:c["end"]][:PREVIEW_CHARS]
        print(f"\n  [{c['label']}] {c['doc_id'].upper()} {c['header']}: {textwrap.shorten(preview, width=300)}")
    if blind:
        return
    print(f"\nflags: {', '.join(row['flag_reasons']) or 'none'}")
    if row.get("judge"):
        j = row["judge"]
        print(f"judge: answerable={j['answerable']} also={j['also_answered_by']} leakage={j['leakage']} category={j['category']}")
        print(textwrap.fill(f"judge reasoning: {j['reasoning']}", width=100))
    if row.get("judge_error"):
        print(f"judge error: {row['judge_error']}")


def calibrate(candidates: list[dict], triage: dict[str, dict], sample_ids: list[str], corpus: dict[str, str],
              labels_path: Path, reviewer: str, input_fn: Callable[[str], str] = input) -> None:
    by_id = {c["candidate_id"]: c for c in candidates}
    labels = load_labels(labels_path)
    eligible = [cid for cid in sample_ids if triage[cid]["status"] != "refused"]
    done = [cid for cid in eligible if labels.get(cid, {}).get("mode") == "calibrate"]
    wrong_mode = [cid for cid in eligible if cid in labels and cid not in done]
    pending = [cid for cid in eligible if cid not in labels]
    print(f"calibration: {len(done)} of {len(eligible)} done")
    for cid in wrong_mode:
        print(f"[{cid}] label mode is {labels[cid].get('mode')!r}, expected 'calibrate': fix that line in {labels_path}; "
              f"it is not shown for labelling because only the first label per candidate counts")
    for cid in pending:
        cand, row = by_id[cid], triage[cid]
        if validate_candidate(cand, corpus):
            print(f"refusing [{cid}]: invalid span")
            continue
        _show(cand, row, corpus, blind=True)
        answerable = _choice(input_fn, "answerable? [y]es [p]artial [n]o, or [q]uit > ", {**ANSWERABLE, "q": "quit"})
        if answerable == "quit":
            return
        also = _competitor_labels(input_fn, {c["label"] for c in row.get("competitors", [])})
        leakage = _choice(input_fn, "leakage? [n]one [s]ome [h]eavy > ", LEAKAGE)
        category = _choice(input_fn, "category? [f]ato_pontual [c]onceito [p]rocedimento > ", CATEGORY_CHOICES)
        decision = _choice(input_fn, "[a]ccept [e]dit question [r]eject > ", {"a": "accept", "e": "edit", "r": "reject"})
        question = cand["question"]
        if decision == "edit":
            question = input_fn("new question > ").strip() or question
            decision = "accept"
        _append(labels_path, {"candidate_id": cid, "mode": "calibrate", "reviewer": reviewer,
                              "reviewed_at": dt.date.today().isoformat(), "decision": decision,
                              "question": question, "category": category,
                              "rubric": {"answerable": answerable, "also_answered_by": also, "leakage": leakage}})


def confirm_items(candidates: list[dict], triage: dict[str, dict], sample_ids: list[str], corpus: dict[str, str],
                  labels_path: Path, reviewer: str, mode: str, input_fn: Callable[[str], str] = input) -> None:
    if mode not in ("flagged", "unflagged"):
        raise ValueError(f"unknown mode {mode!r}")
    by_id = {c["candidate_id"]: c for c in candidates}
    labels = load_labels(labels_path)
    sample = set(sample_ids)
    pending = [cid for cid in sorted(triage)
               if triage[cid]["status"] != "refused" and cid not in sample and cid not in labels
               and bool(triage[cid]["flagged"]) == (mode == "flagged")]
    print(f"{mode}: {len(pending)} pending")
    for cid in pending:
        cand, row = by_id[cid], triage[cid]
        if validate_candidate(cand, corpus):
            print(f"refusing [{cid}]: invalid span")
            continue
        _show(cand, row, corpus, blind=False)
        key, question, category = decide(input_fn, cand["question"], cand["category"])
        if key == "q":
            return
        _append(labels_path, {"candidate_id": cid, "mode": mode, "reviewer": reviewer,
                              "reviewed_at": dt.date.today().isoformat(),
                              "decision": "accept" if key == "a" else "reject",
                              "question": question, "category": category})


def main(mode: str, reviewer: str) -> None:
    triage = load_triage(TRIAGE)
    if not triage:
        sys.exit(f"no triage rows in {TRIAGE}; run evals.groundtruth.golden.triage first")
    if CALIBRATION_SAMPLE.exists():
        sample_ids = json.loads(CALIBRATION_SAMPLE.read_text(encoding="utf-8"))["candidate_ids"]
    else:
        sample_ids = choose_calibration_sample(triage)
        CALIBRATION_SAMPLE.write_text(json.dumps({"seed": CALIBRATION_SEED, "n": CALIBRATION_N,
                                                  "candidate_ids": sample_ids}, indent=2), encoding="utf-8")
    corpus, candidates = load_corpus(), load_candidates()
    if mode == "calibrate":
        calibrate(candidates, triage, sample_ids, corpus, HUMAN_LABELS, reviewer)
        return
    problems = calibration_problems(sample_ids, triage, load_labels(HUMAN_LABELS))
    if problems:
        limit = 10
        shown = problems[:limit] + ([f"... and {len(problems) - limit} more"] if len(problems) > limit else [])
        sys.exit(f"finish the blind calibration sample first: --mode calibrate; fix any wrong-mode label by hand "
                 f"in {HUMAN_LABELS}\n" + "\n".join(f"  {line}" for line in shown))
    confirm_items(candidates, triage, sample_ids, corpus, HUMAN_LABELS, reviewer, mode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["calibrate", "flagged", "unflagged"])
    parser.add_argument("--reviewer", required=True)
    args = parser.parse_args()
    main(args.mode, args.reviewer)
