"""Task 21 ruling 1: decide offline whether a generation answer is a refusal.

A refusal is an answer that says the agent found no basis in the knowledge base or in the documents
and gives no legal content of its own. This module decides that from the answer text alone: no model
call, no embedding, no network, and no length threshold or judge score anywhere in the decision. It
exists because the two metrics the project publishes, DeepEval faithfulness and answer relevancy,
are blind to over-refusal: a refusal asserts nothing, so it contradicts nothing, and `r1-cdc-060` of
the 2026-10-06 run scored 1.00 on both while refusing a question the base does cover.

What it is not. It matches a small set of known phrasings, so a refusal phrased some other way
escapes it and the count is a floor, not a measurement: this detector can undercount. The two-judge
rubric in generation/abstention.py stays the reference for out-of-scope abstention; this is a cheap,
offline guard beside it, not a replacement. It also cannot see a partial refusal: an answer that
carries one of these phrasings and then gives the rule anyway is counted here as a refusal.

Usage (prints the two counts of the committed answers, with no API call):
  .venv/Scripts/python.exe -m evals.groundtruth.generation.refusal
"""
import json
import re
import unicodedata
from dataclasses import dataclass

from evals.groundtruth.config import ANSWERS
from evals.groundtruth.generation.answers import is_failed_run
from evals.groundtruth.generation.run_generation import split_by_kind
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows

# How much of an answer a report or an audit line quotes, per Task 21 ruling 2.
ANSWER_PREFIX_CHARS = 200

# The phrasing Task 20 pinned in JuriAI.INSTRUCTIONS: the agent is told to say, with all the letters,
# that it "nao encontrou base nos documentos da base de conhecimento para responder". The instruction
# is written in the third person and an agent following it writes the first person, so both are
# allowed, and the object is either the documents or the base itself, which the instruction names
# together ("os documentos da base de conhecimento").
NO_BASIS_PINNED = r"nao encontr(?:ei|ou|amos) base (?:nos documentos|na base de conhecimento)"

# The variant every refusal in the committed 2026-10-06 answers actually produced: it says it found
# no information in the knowledge base. What sits between "informacoes" and "na base de conhecimento"
# differs across the rows (nothing in oos-03, "especificas" in oos-01), and oos-02 and oos-09 put
# their qualifier after the base instead, so the gap is bounded rather than enumerated: at most 60
# characters and never across a sentence end, so two unrelated sentences cannot combine into a match.
NO_INFORMATION_IN_BASE = r"nao encontrei informac\w*[^.!?]{0,60}?na base de conhecimento"

# The documents wording of the same sentence. No row of the 2026-10-06 run phrased it this way; it is
# here because the pinned instruction names the documents, so an answer can say it found nothing in
# them rather than in the base.
NO_INFORMATION_IN_DOCUMENTS = r"nao encontrei informac\w*[^.!?]{0,60}?nos documentos"

PHRASINGS = (
    ("no_basis_pinned", NO_BASIS_PINNED),
    ("no_information_in_base", NO_INFORMATION_IN_BASE),
    ("no_information_in_documents", NO_INFORMATION_IN_DOCUMENTS),
)
_COMPILED = tuple((name, re.compile(pattern)) for name, pattern in PHRASINGS)


@dataclass(frozen=True)
class RefusalVerdict:
    """phrasing and matched_text are the audit trail: the name of the constant that fired and the
    exact normalized span it matched, so a human can check a verdict without rerunning anything."""

    is_refusal: bool
    phrasing: str | None
    matched_text: str | None


def normalize(text: str | None) -> str:
    """Casefolded, accent-stripped, whitespace-collapsed text.

    An answer may arrive accented or not, and agno's output wraps, so a phrase can be split across
    lines. Stripping combining marks after NFD makes "Não" and "Nao" the same string, and collapsing
    runs of whitespace keeps a reflowed sentence matchable.
    """
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


def detect_refusal(answer: str | None) -> RefusalVerdict:
    """The first phrasing that matches, in PHRASINGS order, or a non-refusal verdict."""
    text = normalize(answer)
    for name, pattern in _COMPILED:
        match = pattern.search(text)
        if match is not None:
            return RefusalVerdict(True, name, match.group(0))
    return RefusalVerdict(False, None, None)


def row_verdict(row: dict) -> dict:
    """One answers.jsonl row judged, as a dict a report can print.

    A failed agent run is never a refusal: its "answer" is the error text agno put there, not
    something the agent chose to say, so the decision is made before any phrasing is looked at.
    is_failed_run covers both the modern run_failed field and the legacy pre-adoption rows that
    predate it.
    """
    answer = row.get("answer") or ""
    prefix = answer[:ANSWER_PREFIX_CHARS]
    if is_failed_run(row):
        return {"id": row["id"], "run_failed": True, "is_refusal": False, "phrasing": None,
                "matched_text": None, "answer_prefix": prefix}
    verdict = detect_refusal(answer)
    return {"id": row["id"], "run_failed": False, "is_refusal": verdict.is_refusal,
            "phrasing": verdict.phrasing, "matched_text": verdict.matched_text, "answer_prefix": prefix}


def row_verdicts(rows: list[dict]) -> list[dict]:
    """One verdict per row, in the order given."""
    return [row_verdict(row) for row in rows]


def count_refusals(rows: list[dict]) -> int:
    return sum(1 for verdict in row_verdicts(rows) if verdict["is_refusal"])


def refusal_counts(rows: list[dict]) -> dict:
    """The two gated counts and their n, from one answers.jsonl row list.

    Split golden from out-of-scope with run_generation.split_by_kind, so this reads the same category
    field the run itself wrote and cannot drift from it.
    """
    golden_rows, oos_rows = split_by_kind(rows)
    return {"n_golden": len(golden_rows), "n_out_of_scope": len(oos_rows),
            "golden_refusals": count_refusals(golden_rows),
            "out_of_scope_refusals": count_refusals(oos_rows)}


def judge_agreement(oos_rows: list[dict], stored_abstention: list[dict]) -> dict:
    """How often this detector and the two-judge label agree on the out-of-scope rows.

    stored_abstention is the "abstention" list of generation/scores.json, whose per-row label comes
    from abstention_label: "abstained" only when both judges said yes. Every other label
    ("answered", "disagreement", "unverified", "run_failed") counts here as not abstained, because
    none of them is a confirmed abstention.

    Returns n, agree, and one entry per disagreement naming the id, both sides and the first
    ANSWER_PREFIX_CHARS characters of the answer, so a reader can judge the row themselves. Raises
    when a row has no stored label at all: silently scoring it as agreement would inflate the number
    this task publishes.
    """
    labels = {item["id"]: item["label"] for item in stored_abstention}
    missing = [row["id"] for row in oos_rows if row["id"] not in labels]
    if missing:
        raise ValueError(f"no stored abstention label in scores.json for {', '.join(missing)}; "
                         "the agreement cannot be computed without both sides")
    agree = 0
    disagreements = []
    for row, verdict in zip(oos_rows, row_verdicts(oos_rows)):
        label = labels[row["id"]]
        judged_abstained = label == "abstained"
        if verdict["is_refusal"] == judged_abstained:
            agree += 1
            continue
        disagreements.append({"id": row["id"], "detector_refusal": verdict["is_refusal"],
                              "judge_label": label, "answer_prefix": verdict["answer_prefix"]})
    return {"n": len(oos_rows), "agree": agree, "disagreements": disagreements}


def main() -> None:
    counts = refusal_counts(read_jsonl_rows(ANSWERS))
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
