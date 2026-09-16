"""Verify that the 10 out-of-scope questions cannot be answered from the corpus.

Each question is checked against the union of its BM25 top 5 and text-embedding-3-large top 5 competitor
articles (the same candidate_articles pool the golden triage draws from) by two independent-vendor
judges, gpt-4.1 and claude-haiku-4-5, mirroring the rubric-v2 dual-judge pattern used for the golden set.
A question counts as out of scope only when both judges agree that none of the checked articles contains
any part of the answer.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.generation.out_of_scope_check
"""
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from evals.groundtruth.config import CACHE_DIR, OUT_OF_SCOPE, OUT_OF_SCOPE_CHECK, OUT_OF_SCOPE_REPORT, load_corpus
from evals.groundtruth.golden.competitors import (COMPETITOR_DIMENSIONS, COMPETITOR_MODEL, BM25, article_refs,
                                                  embed_articles, find_competitors)
from evals.groundtruth.golden.judges import ANTHROPIC_JUDGE_MODEL, ANTHROPIC_MAX_TOKENS
from evals.groundtruth.golden.leakage import content_tokens
from evals.groundtruth.golden.triage import JUDGE_MODEL, MAX_JUDGE_ATTEMPTS, JudgeError, _response_content

CHECK_VERSION = "v1"
ARTICLE_MAX_CHARS = 8000

PROMPT = """Você verifica se uma pergunta pode ser respondida pelos artigos de uma base de legislação.
Julgue apenas com o texto fornecido nos ARTIGOS, sem nenhum conhecimento externo.

Responda em JSON com exatamente estas chaves, nesta ordem:
- "reasoning": 2 a 4 frases com a sua análise. Escreva esta chave antes de decidir as demais.
- "answered_by": lista com os rótulos, como "C1", dos ARTIGOS cujo texto, sozinho, contém a resposta
  completa à pergunta.
- "partially_answered_by": lista com os rótulos dos ARTIGOS cujo texto contém parte da resposta, ou uma
  regra que decide a pergunta, sem conter a resposta completa. Tratar de tema parecido sem responder não
  conta.

As duas listas ficam vazias quando nenhum artigo responde. Use apenas os rótulos listados abaixo, e um
mesmo rótulo não pode aparecer nas duas listas.

PERGUNTA:
{question}

ARTIGOS:
{articles}
"""


class OutOfScopeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    answered_by: list[str]
    partially_answered_by: list[str]

    @field_validator("reasoning")
    @classmethod
    def reasoning_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning must not be blank")
        return value

    @model_validator(mode="after")
    def no_label_in_both_lists(self):
        overlap = sorted(set(self.answered_by) & set(self.partially_answered_by))
        if overlap:
            raise ValueError(f"label(s) {overlap} appear in both answered_by and partially_answered_by")
        return self


REQUIRED_KEYS = {"id", "question", "category", "expected_source"}


def load_out_of_scope(path: Path) -> list[dict]:
    """Load and validate the out-of-scope questions. Raises ValueError on any malformed row."""
    items = []
    seen_ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        missing = REQUIRED_KEYS - set(row)
        if missing:
            raise ValueError(f"row missing key(s) {sorted(missing)}: {row}")
        if row["id"] in seen_ids:
            raise ValueError(f"duplicate id {row['id']!r}")
        seen_ids.add(row["id"])
        if row["category"] != "fora_de_escopo":
            raise ValueError(f"{row['id']}: category must be 'fora_de_escopo', got {row['category']!r}")
        if not row["question"].strip():
            raise ValueError(f"{row['id']}: question must not be blank")
        items.append(row)
    return items


def candidate_articles(question: str, refs, bm25: BM25, question_vector: np.ndarray,
                       article_matrix: np.ndarray) -> list[dict]:
    """The BM25 top 5 + dense top 5 competitor articles for question, labelled C1, C2, ... in order.

    golden_index=-1 because there is no golden article for an out-of-scope question, so nothing is excluded.
    """
    competitors = find_competitors(question, -1, refs, bm25, question_vector, article_matrix)
    articles = []
    for n, c in enumerate(competitors, start=1):
        articles.append({"ref_id": c["ref_id"], "doc_id": c["doc_id"], "header": c["header"],
                         "start": c["start"], "end": c["end"], "methods": c["methods"], "label": f"C{n}"})
    return articles


def article_block(articles: list[dict], corpus: dict[str, str]) -> str:
    blocks = []
    for a in articles:
        text = corpus[a["doc_id"]][a["start"]:a["end"]]
        preview = text[:ARTICLE_MAX_CHARS] + (" [...]" if len(text) > ARTICLE_MAX_CHARS else "")
        blocks.append(f"[{a['label']}] {a['doc_id'].upper()} {a['header']}: {preview}")
    return "\n\n".join(blocks)


def _prompt_content(question: str, articles: list[dict], corpus: dict[str, str]) -> str:
    return PROMPT.format(question=question, articles=article_block(articles, corpus))


def openai_check(client, question: str, articles: list[dict], corpus: dict[str, str]
                 ) -> tuple[OutOfScopeVerdict, dict]:
    labels = {a["label"] for a in articles}
    content = _prompt_content(question, articles, corpus)
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        # Only a bad model output counts as a failed attempt; transport and API errors propagate, same as
        # golden/triage.py judge().
        response = client.chat.completions.create(
            model=JUDGE_MODEL, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}])
        try:
            verdict = OutOfScopeVerdict.model_validate(json.loads(_response_content(response)))
        except ValueError as exc:  # JSONDecodeError and pydantic ValidationError are both ValueError
            last_error = str(exc)
            continue
        unknown = sorted((set(verdict.answered_by) | set(verdict.partially_answered_by)) - labels)
        if unknown:
            last_error = f"unknown labels {unknown}"
            continue
        usage = response.usage
        return verdict, {"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens}
    raise JudgeError(f"{JUDGE_MODEL} failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


def anthropic_check(client, question: str, articles: list[dict], corpus: dict[str, str]
                    ) -> tuple[OutOfScopeVerdict, dict]:
    labels = {a["label"] for a in articles}
    content = _prompt_content(question, articles, corpus)
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        try:
            # anthropic 1.x removed sampling parameters from its signatures, but the API still honours them for
            # Haiku 4.5, and the spec requires temperature 0, so it goes in extra_body.
            response = client.messages.parse(
                model=ANTHROPIC_JUDGE_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS,
                messages=[{"role": "user", "content": content}], output_format=OutOfScopeVerdict,
                extra_body={"temperature": 0})
        except ValueError as exc:  # the parsed output failed OutOfScopeVerdict validation
            last_error = str(exc)
            continue
        if response.stop_reason != "end_turn":
            last_error = f"stop_reason {response.stop_reason}"
            continue
        verdict = response.parsed_output
        if not isinstance(verdict, OutOfScopeVerdict):
            last_error = "response carried no parsed verdict"
            continue
        unknown = sorted((set(verdict.answered_by) | set(verdict.partially_answered_by)) - labels)
        if unknown:
            last_error = f"unknown labels {unknown}"
            continue
        usage = response.usage
        return verdict, {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}
    raise JudgeError(f"{ANTHROPIC_JUDGE_MODEL} failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


CHECKS = {JUDGE_MODEL: openai_check, ANTHROPIC_JUDGE_MODEL: anthropic_check}


def status_for(judges: dict) -> str:
    verdicts = []
    for info in judges.values():
        if info.get("error") or info.get("verdict") is None:
            return "unverified"
        verdicts.append(info["verdict"])
    for verdict in verdicts:
        if verdict.get("answered_by") or verdict.get("partially_answered_by"):
            return "answerable"
    return "out_of_scope"


def run_check(items: list[dict], corpus: dict[str, str], refs, bm25: BM25, question_embedder,
             article_matrix: np.ndarray, clients: dict) -> list[dict]:
    rows = []
    for item in items:
        qvec = np.asarray(question_embedder.get_embedding(item["question"]), dtype=np.float32)
        norm = float(np.linalg.norm(qvec))
        if norm == 0:
            raise ValueError(f"zero-norm question embedding for {item['id']}")
        articles = candidate_articles(item["question"], refs, bm25, qvec / norm, article_matrix)
        judges = {}
        for model, check_fn in CHECKS.items():
            try:
                verdict, usage = check_fn(clients[model], item["question"], articles, corpus)
                judges[model] = {"verdict": verdict.model_dump(), "error": None, "usage": usage}
            except JudgeError as exc:
                judges[model] = {"verdict": None, "error": str(exc), "usage": None}
        rows.append({"id": item["id"], "question": item["question"], "check_version": CHECK_VERSION,
                    "checked_at": dt.date.today().isoformat(), "articles": articles, "judges": judges,
                    "status": status_for(judges)})
    return rows


def _judge_cell(info: dict) -> str:
    if info.get("error"):
        return "error"
    verdict = info.get("verdict") or {}
    complete = ",".join(verdict.get("answered_by", [])) or "none"
    partial = ",".join(verdict.get("partially_answered_by", [])) or "none"
    return f"{complete} / {partial}"


def render_report(rows: list[dict]) -> str:
    lines = ["# Out-of-scope question check", "",
            "A question counts as out of scope only when both judges agree that none of the checked "
            "articles, complete or partial, contains any part of the answer.", "",
            "| id | question | articles checked | gpt-4.1 (complete / partial) | "
            "claude-haiku-4-5 (complete / partial) | status |",
            "|---|---|---|---|---|---|"]
    for row in rows:
        oa = row["judges"].get(JUDGE_MODEL, {})
        an = row["judges"].get(ANTHROPIC_JUDGE_MODEL, {})
        lines.append(f"| {row['id']} | {row['question']} | {len(row['articles'])} | {_judge_cell(oa)} | "
                    f"{_judge_cell(an)} | {row['status']} |")
    lines.append("")
    counts = Counter(row["status"] for row in rows)
    lines.append("## Status counts")
    lines.append("")
    for status in ("out_of_scope", "answerable", "unverified"):
        lines.append(f"- {status}: {counts.get(status, 0)}")
    lines.append("")
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0})
    for row in rows:
        for model, info in row["judges"].items():
            usage = info.get("usage")
            if usage:
                totals[model]["input_tokens"] += usage["input_tokens"]
                totals[model]["output_tokens"] += usage["output_tokens"]
    lines.append("## Token totals")
    lines.append("")
    for model in (JUDGE_MODEL, ANTHROPIC_JUDGE_MODEL):
        t = totals[model]
        lines.append(f"- {model}: input {t['input_tokens']}, output {t['output_tokens']}")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "Only the union of BM25 top 5 and text-embedding-3-large top 5 articles is checked, so a relevant "
        "article that neither method surfaces is never shown to the judges. Article text is capped at 8000 "
        "characters, so a very long article is truncated before it reaches the judges. The judges come from "
        "two vendors, gpt-4.1 and claude-haiku-4-5, and there is no human legal review of these verdicts.")
    return "\n".join(lines) + "\n"


def main() -> None:
    import anthropic
    from dotenv import load_dotenv
    from openai import OpenAI

    from evals.groundtruth.embedder_cache import openai_embedder

    load_dotenv()
    corpus = load_corpus()
    items = load_out_of_scope(OUT_OF_SCOPE)
    refs = article_refs(corpus)
    bm25 = BM25([content_tokens(corpus[r.doc_id][r.start:r.end]) for r in refs])
    articles_embedder = openai_embedder(COMPETITOR_MODEL, COMPETITOR_DIMENSIONS, CACHE_DIR / "triage" / "articles",
                                        online=True)
    questions_embedder = openai_embedder(COMPETITOR_MODEL, COMPETITOR_DIMENSIONS, CACHE_DIR / "triage" / "questions",
                                         online=True)
    matrix = embed_articles(refs, corpus, articles_embedder)
    clients = {JUDGE_MODEL: OpenAI(), ANTHROPIC_JUDGE_MODEL: anthropic.Anthropic()}

    rows = run_check(items, corpus, refs, bm25, questions_embedder, matrix, clients)

    questions_embedder.save()
    articles_embedder.save()

    OUT_OF_SCOPE_CHECK.parent.mkdir(parents=True, exist_ok=True)
    with OUT_OF_SCOPE_CHECK.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    OUT_OF_SCOPE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_OF_SCOPE_REPORT.write_text(render_report(rows), encoding="utf-8")

    counts = Counter(row["status"] for row in rows)
    print(json.dumps(counts))
    if any(row["status"] != "out_of_scope" for row in rows):
        sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
