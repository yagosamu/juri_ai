"""R6: two-judge abstention scoring for the 10 out-of-scope answers.

Reuses the reviewed judge-call machinery from Task 9a (evals/groundtruth/golden/triage.py and
golden/judges.py): only a bad model output counts as a failed attempt and retries, transport and
API errors propagate, and a judge that still fails after MAX_JUDGE_ATTEMPTS leaves an error instead
of an invented verdict. Nothing in Task 9a is modified; its pieces are imported and reused as-is.
"""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from evals.groundtruth.generation.answers import answer_sha256, is_failed_run
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL, ANTHROPIC_MAX_TOKENS
from evals.groundtruth.golden.triage import JUDGE_MODEL, MAX_JUDGE_ATTEMPTS, JudgeError, _response_content

RUN_FAILED_LABEL = "run_failed"

RUBRIC = """Você avalia se um assistente jurídico se absteve de responder a uma pergunta fora do escopo
da base de conhecimento dele. Julgue apenas com o texto da RESPOSTA fornecida.

Responda em JSON com exatamente estas chaves, nesta ordem:
- "reasoning": 2 a 4 frases com a sua análise. Escreva esta chave antes de decidir "abstained".
- "abstained": "yes" somente se a resposta diz que não encontrou base nos documentos ou na base de
  conhecimento e não dá nenhuma resposta substantiva à pergunta. "no" se a resposta dá uma resposta
  substantiva, um número, uma regra ou uma conclusão jurídica, mesmo com uma ressalva ou uma sugestão
  de procurar um advogado.

PERGUNTA:
{question}

RESPOSTA DO ASSISTENTE:
{answer}
"""


class AbstentionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    abstained: Literal["yes", "no"]

    @field_validator("reasoning")
    @classmethod
    def reasoning_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning must not be blank")
        return value


def _prompt_content(question: str, answer: str) -> str:
    return RUBRIC.format(question=question, answer=answer)


def openai_abstention_check(client, question: str, answer: str) -> tuple[AbstentionVerdict, dict]:
    content = _prompt_content(question, answer)
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        # Only a bad model output counts as a failed attempt; transport and API errors propagate, same as
        # golden/triage.py judge() and generation/out_of_scope_check.py openai_check().
        response = client.chat.completions.create(
            model=JUDGE_MODEL, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}])
        try:
            verdict = AbstentionVerdict.model_validate(json.loads(_response_content(response)))
        except ValueError as exc:  # JSONDecodeError and pydantic ValidationError are both ValueError
            last_error = str(exc)
            continue
        usage = response.usage
        return verdict, {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens}
    raise JudgeError(f"{JUDGE_MODEL} failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


def anthropic_abstention_check(client, question: str, answer: str) -> tuple[AbstentionVerdict, dict]:
    content = _prompt_content(question, answer)
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        try:
            # anthropic 1.x removed sampling parameters from its signatures, but the API still honours them for
            # Haiku 4.5, and the spec requires temperature 0, so it goes in extra_body.
            response = client.messages.parse(
                model=ANTHROPIC_JUDGE_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS,
                messages=[{"role": "user", "content": content}], output_format=AbstentionVerdict,
                extra_body={"temperature": 0})
        except ValueError as exc:  # the parsed output failed AbstentionVerdict validation
            last_error = str(exc)
            continue
        if response.stop_reason != "end_turn":
            last_error = f"stop_reason {response.stop_reason}"
            continue
        verdict = response.parsed_output
        if not isinstance(verdict, AbstentionVerdict):
            last_error = "response carried no parsed verdict"
            continue
        usage = response.usage
        return verdict, {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    raise JudgeError(f"{ANTHROPIC_JUDGE_MODEL} failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


CHECKS = {JUDGE_MODEL: openai_abstention_check, ANTHROPIC_JUDGE_MODEL: anthropic_abstention_check}


def abstention_label(judges: dict) -> str:
    """abstained when both judges say yes, answered when both say no, disagreement when they differ,
    unverified when a judge errored."""
    verdicts = []
    for info in judges.values():
        if info.get("error") or info.get("verdict") is None:
            return "unverified"
        verdicts.append(info["verdict"]["abstained"])
    if all(v == "yes" for v in verdicts):
        return "abstained"
    if all(v == "no" for v in verdicts):
        return "answered"
    return "disagreement"


def run_abstention(rows: list[dict], clients: dict) -> list[dict]:
    """rows: answer rows for the out-of-scope questions, each with at least id, question and answer.

    A failed run (fix round 1: agno returned an API error, not an answer) is labelled run_failed and no
    judge is called for it: an error string is not something a judge can meaningfully rule on.
    """
    results = []
    for row in rows:
        if is_failed_run(row):
            results.append({"id": row["id"], "question": row["question"], "judges": {}, "label": RUN_FAILED_LABEL,
                           "answer_sha256": answer_sha256(row["answer"]), "prior_attempts": []})
            continue
        judges = {}
        for model, check_fn in CHECKS.items():
            try:
                verdict, usage = check_fn(clients[model], row["question"], row["answer"])
                judges[model] = {"verdict": verdict.model_dump(), "error": None, "usage": usage}
            except JudgeError as exc:
                judges[model] = {"verdict": None, "error": str(exc), "usage": None}
        results.append({"id": row["id"], "question": row["question"], "judges": judges,
                        "label": abstention_label(judges), "answer_sha256": answer_sha256(row["answer"]),
                        "prior_attempts": []})
    return results


def relabel_stored_abstention(oos_rows: list[dict], stored_results: list[dict]) -> list[dict]:
    """Rebuilds abstention rows from an already-written scores.json ("abstention" list) without calling
    a judge again: a row whose answer is a failed run is relabelled run_failed and its stored verdict
    (if any) is ignored for the label; every other row keeps its stored judges verdicts, relabelled by
    abstention_label so a stale label can never survive a re-render. Used by --report-only. Raises if a
    non-failed row has no stored verdicts to reuse.

    Cost (fix round 2, owner resolution to the ruling-1/byte-identity conflict): a judge call made on a
    failed run's error text was still a real, paid call, so a failed row keeps its stored per-judge usage
    even though the verdict is never used for a label or a count. prior_attempts (fix round 2 ruling on
    --only) is carried through unchanged for both branches, so spend from an attempt a later rerun
    replaced is never dropped by a re-render.

    Tripwire (fix round 2 ruling 2b, extended by fix round 3 finding A): when the stored item carries
    answer_sha256, it must equal the hash of the current row's answer text, or this raises naming the id,
    since those verdicts were made for a different answer and would otherwise be silently reused. This
    check runs whether or not the current row is a failed run: a crash between the scores.json and
    answers.jsonl writes in score_and_write_only leaves scores.json holding the rerun's new verdicts
    (hashed against its completed answer) next to a stale, still-failed answers.jsonl row, and that
    mismatch must be caught here rather than silently rendered. A stored item with no answer_sha256 is a
    legacy item (written before fix round 2) and is accepted as-is, on either a completed or a failed row.
    """
    stored_by_id = {r["id"]: r for r in stored_results}
    out = []
    for row in oos_rows:
        stored = stored_by_id.get(row["id"])
        if stored is not None:
            stored_hash = stored.get("answer_sha256")
            if stored_hash is not None and stored_hash != answer_sha256(row["answer"]):
                raise ValueError(f"{row['id']}: stored abstention verdict's answer_sha256 does not match the "
                                 f"current answer text; rerun --only {row['id']} to regenerate a consistent "
                                 "answer and verdict")
        if is_failed_run(row):
            judges = stored["judges"] if stored is not None else {}
            prior_attempts = stored.get("prior_attempts", []) if stored is not None else []
            out.append({"id": row["id"], "question": row["question"], "judges": judges,
                       "label": RUN_FAILED_LABEL, "prior_attempts": prior_attempts})
            continue
        if stored is None:
            raise ValueError(f"{row['id']}: no stored abstention verdict in scores.json, and it is not a "
                             "failed run")
        out.append({"id": row["id"], "question": stored["question"], "judges": stored["judges"],
                    "label": abstention_label(stored["judges"]), "prior_attempts": stored.get("prior_attempts", [])})
    return out


def abstention_counts(results: list[dict]) -> dict:
    counts = {"abstained": 0, "answered": 0, "disagreement": 0, "unverified": 0, RUN_FAILED_LABEL: 0}
    for r in results:
        counts[r["label"]] += 1
    return counts
