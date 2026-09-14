"""LLM triage of golden-set candidates.

Deterministic leakage signals, competitor articles from two independent search methods, and a rubric
judge that writes its reasoning before its verdict. The judge never sees the candidate's stored
category. Its output is advisory: flag_reasons decides what a human must look at, and nothing becomes
a golden item here.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.triage [--smoke] [--limit N] [--force]
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator

from evals.groundtruth.config import CACHE_DIR, TRIAGE, load_corpus
from evals.groundtruth.golden.competitors import (COMPETITOR_DIMENSIONS, COMPETITOR_MODEL, BM25, article_refs,
                                                  embed_articles, find_competitors)
from evals.groundtruth.golden.jsonl_io import drop_malformed_tail, read_jsonl_rows
from evals.groundtruth.golden.leakage import NGRAM_FLAG, content_tokens, leakage_signals
from evals.groundtruth.golden.review import load_candidates, validate_candidate
from evals.groundtruth.golden.schema import Category

JUDGE_MODEL = "gpt-4.1"
PREVIEW_CHARS = 1500
MAX_JUDGE_ATTEMPTS = 2

PROMPT = """Você avalia um candidato a gabarito de um benchmark de busca jurídica. Um sistema de busca
vai receber a PERGUNTA e precisa encontrar o ARTIGO. Julgue apenas com o texto fornecido.

Responda em JSON com exatamente estas chaves, nesta ordem:
- "reasoning": 2 a 4 frases com a sua análise. Escreva esta chave antes de decidir as demais.
- "answerable": "yes" se o ARTIGO sozinho responde a pergunta por completo; "partial" se responde só
  parte ou depende de outro dispositivo; "no" se não responde.
- "also_answered_by": lista com os rótulos, como "C2", dos ARTIGOS CONCORRENTES que também respondem a
  pergunta por completo, sozinhos. Lista vazia se nenhum responde. Use apenas rótulos listados abaixo.
- "leakage": "none" se a pergunta soa natural; "some" se reaproveita alguns termos distintivos do
  artigo; "heavy" se copia frase ou estrutura do artigo, ou se refere a um artigo ou dispositivo que
  quem pergunta não teria em mãos.
- "category": "fato_pontual" para prazo, valor, número ou quem; "conceito" para definição ou o que é;
  "procedimento" para como fazer, etapas ou requisitos.

PERGUNTA:
{question}

ARTIGO {header}:
{article}

ARTIGOS CONCORRENTES:
{competitors}
"""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    answerable: Literal["yes", "partial", "no"]
    also_answered_by: list[str]
    leakage: Literal["none", "some", "heavy"]
    category: Category

    @field_validator("reasoning")
    @classmethod
    def reasoning_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning must not be blank")
        return value


class JudgeError(RuntimeError):
    pass


def competitor_block(competitors: list[dict], corpus: dict[str, str]) -> str:
    if not competitors:
        return "nenhum"
    blocks = []
    for c in competitors:
        text = corpus[c["doc_id"]][c["start"]:c["end"]]
        preview = text[:PREVIEW_CHARS] + (" [...]" if len(text) > PREVIEW_CHARS else "")
        blocks.append(f"[{c['label']}] {c['doc_id'].upper()} {c['header']}: {preview}")
    return "\n\n".join(blocks)


def _response_content(response) -> str:
    """The first choice's message content. ValueError when the response carries no usable string content."""
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("response has no choices")
    content = getattr(getattr(choices[0], "message", None), "content", None)
    if not isinstance(content, str):
        raise ValueError(f"response content is {type(content).__name__}, not a string")
    return content


def judge(client, question: str, header: str, article: str, competitors: list[dict],
          corpus: dict[str, str]) -> JudgeVerdict:
    labels = {c["label"] for c in competitors}
    content = PROMPT.format(question=question, header=header, article=article,
                            competitors=competitor_block(competitors, corpus))
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        # Only a bad model output counts as a failed attempt: an unusable response shape, invalid JSON or a
        # verdict that breaks the schema. Transport and API errors (openai.APIError: connection, timeout, rate
        # limit, HTTP status) propagate on purpose: the run stops, no row is written, and a rerun judges the
        # candidate again instead of leaving a good candidate marked judge_failed over a transient failure.
        response = client.chat.completions.create(
            model=JUDGE_MODEL, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": content}])
        try:
            verdict = JudgeVerdict.model_validate(json.loads(_response_content(response)))
        except ValueError as exc:  # JSONDecodeError and pydantic ValidationError are both ValueError
            last_error = str(exc)
            continue
        unknown = sorted(set(verdict.also_answered_by) - labels)
        if unknown:
            last_error = f"unknown competitor labels {unknown}"
            continue
        return verdict
    raise JudgeError(f"judge failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


def flag_reasons(stored_category: str, verdict: JudgeVerdict | None, signals: dict,
                 judge_error: str | None) -> list[str]:
    reasons = []
    if signals["cites_source"]:
        reasons.append("cites_source")
    if signals["max_shared_ngram"] >= NGRAM_FLAG:
        reasons.append(f"shared_ngram={signals['max_shared_ngram']}")
    if judge_error:
        reasons.append(f"judge_failed: {judge_error}")
        return reasons
    if verdict.answerable != "yes":
        reasons.append(f"answerable={verdict.answerable}")
    if verdict.also_answered_by:
        reasons.append("also_answered_by=" + ",".join(verdict.also_answered_by))
    if verdict.leakage == "heavy":
        reasons.append("leakage=heavy")
    if verdict.category != stored_category:
        reasons.append(f"category_mismatch: stored={stored_category} judge={verdict.category}")
    return reasons


def load_triage(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for row in read_jsonl_rows(path):
        rows.setdefault(row["candidate_id"], row)
    return rows


def rederive_flags(rows: list[dict], candidates: list[dict], corpus: dict[str, str]) -> list[dict]:
    """Recompute signals, flag_reasons and flagged from each row's stored verdict, with no model call.

    For when a deterministic rule changes after a run. Every other field, including judge, judge_error,
    competitors, judge_model, judged_at and status, is copied unchanged; refused rows are returned as they are.
    """
    by_id = {c["candidate_id"]: c for c in candidates}
    rederived = []
    for row in rows:
        if row["status"] == "refused":
            rederived.append(dict(row))
            continue
        cand = by_id[row["candidate_id"]]
        signals = leakage_signals(cand["question"], corpus[cand["doc_id"]][cand["start"]:cand["end"]])
        verdict = JudgeVerdict.model_validate(row["judge"]) if row["judge"] is not None else None
        reasons = flag_reasons(cand["category"], verdict, signals, row["judge_error"])
        rederived.append({**row, "signals": signals, "flag_reasons": reasons, "flagged": bool(reasons)})
    return rederived


def rederive_file(path: Path, candidates: list[dict], corpus: dict[str, str]) -> list[tuple[str, list[str], list[str]]]:
    """Rewrite a triage file with rederived flags. Returns (candidate_id, before, after) for each changed flag list."""
    old = read_jsonl_rows(path)
    new = rederive_flags(old, candidates, corpus)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in new:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return [(after["candidate_id"], before["flag_reasons"], after["flag_reasons"])
            for before, after in zip(old, new) if before["flag_reasons"] != after["flag_reasons"]]


def run_triage(candidates: list[dict], corpus: dict[str, str], client, question_embedder,
               article_matrix: np.ndarray, refs, out_path: Path, force: bool = False,
               limit: int | None = None) -> dict:
    if force and out_path.exists():
        out_path.unlink()
    drop_malformed_tail(out_path)
    done = load_triage(out_path)
    index_by_start = {(r.doc_id, r.start): i for i, r in enumerate(refs)}
    bm25 = BM25([content_tokens(corpus[r.doc_id][r.start:r.end]) for r in refs])
    todo = [c for c in candidates if c["candidate_id"] not in done]
    counts = {"judged": 0, "judge_failed": 0, "refused": 0, "skipped_existing": len(candidates) - len(todo)}
    if limit is not None:
        todo = todo[:limit]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as out:
        for cand in todo:
            row = {"candidate_id": cand["candidate_id"], "judge_model": JUDGE_MODEL,
                   "judged_at": dt.date.today().isoformat()}
            error = validate_candidate(cand, corpus)
            golden_index = index_by_start.get((cand.get("doc_id"), cand.get("start")))
            if error is None and golden_index is None:
                error = "candidate span does not start at an article boundary"
            if error:
                row.update(status="refused", refused_reason=error, flagged=False, flag_reasons=[])
            else:
                article = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
                signals = leakage_signals(cand["question"], article)
                qvec = np.asarray(question_embedder.get_embedding(cand["question"]), dtype=np.float32)
                norm = float(np.linalg.norm(qvec))
                if norm == 0:
                    raise ValueError(f"zero-norm question embedding for {cand['candidate_id']}")
                competitors = find_competitors(cand["question"], golden_index, refs, bm25, qvec / norm, article_matrix)
                for n, competitor in enumerate(competitors, start=1):
                    competitor["label"] = f"C{n}"
                verdict, judge_error = None, None
                try:
                    verdict = judge(client, cand["question"], cand["header"], article, competitors, corpus)
                except JudgeError as exc:
                    judge_error = str(exc)
                reasons = flag_reasons(cand["category"], verdict, signals, judge_error)
                row.update(status="judge_failed" if judge_error else "judged", signals=signals,
                           competitors=competitors, judge=verdict.model_dump() if verdict else None,
                           judge_error=judge_error, flag_reasons=reasons, flagged=bool(reasons))
            counts[row["status"]] += 1
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
    question_embedder.save()
    return counts


def main(smoke: bool, limit: int | None, force: bool, rederive: bool = False) -> None:
    if rederive:  # deterministic: no dotenv, no OpenAI client, no API call
        changes = rederive_file(TRIAGE, load_candidates(), load_corpus())
        for candidate_id, before, after in changes:
            print(f"{candidate_id}: {before} -> {after}")
        rows = read_jsonl_rows(TRIAGE)
        print(json.dumps({"rows": len(rows), "changed": len(changes), "flagged": sum(r["flagged"] for r in rows)}))
        return
    from dotenv import load_dotenv
    from openai import OpenAI

    from evals.groundtruth.embedder_cache import openai_embedder

    load_dotenv()
    corpus = load_corpus()
    candidates = load_candidates()
    client = OpenAI()
    if smoke:
        cand = candidates[0]
        article = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
        print(judge(client, cand["question"], cand["header"], article, [], corpus).model_dump_json(indent=2))
        return
    refs = article_refs(corpus)
    articles = openai_embedder(COMPETITOR_MODEL, COMPETITOR_DIMENSIONS, CACHE_DIR / "triage" / "articles", online=True)
    questions = openai_embedder(COMPETITOR_MODEL, COMPETITOR_DIMENSIONS, CACHE_DIR / "triage" / "questions", online=True)
    matrix = embed_articles(refs, corpus, articles)
    print(json.dumps(run_triage(candidates, corpus, client, questions, matrix, refs, TRIAGE, force=force, limit=limit)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="one judge call on the first candidate, no embeddings")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="discard triage.jsonl and judge every candidate again")
    parser.add_argument("--rederive-flags", action="store_true",
                        help="recompute signals and flags from the stored verdicts and rewrite triage.jsonl; no API call")
    args = parser.parse_args()
    main(args.smoke, args.limit, args.force, args.rederive_flags)
