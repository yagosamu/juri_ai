"""Rubric v2 dual-judge run for the golden set, decision 13 of the spec.

Two judges from different vendors, gpt-4.1 and claude-haiku-4-5, apply the same operationally defined rubric
to the same evidence: the question, the golden article and the competitors triage.jsonl already recorded,
with the same labels and previews. Each judge is blind to the other and to the stored category. A judge that
cannot produce a valid verdict leaves an error, never an invented verdict.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.judges [--smoke] [--limit N]
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from evals.groundtruth.config import JUDGMENTS, TRIAGE, load_corpus
from evals.groundtruth.golden.jsonl_io import drop_malformed_tail, read_jsonl_rows
from evals.groundtruth.golden.review import load_candidates, validate_candidate
from evals.groundtruth.golden.triage import JUDGE_MODEL as OPENAI_JUDGE_MODEL
from evals.groundtruth.golden.triage import MAX_JUDGE_ATTEMPTS, JudgeError, JudgeVerdict, competitor_block, judge, load_triage

RUBRIC_VERSION = "v2"
ANTHROPIC_JUDGE_MODEL = "claude-haiku-4-5"
ANTHROPIC_MAX_TOKENS = 2048

RUBRIC_V2 = """Você avalia um candidato a gabarito de um benchmark de busca jurídica. Um sistema de busca
vai receber a PERGUNTA e precisa encontrar o ARTIGO. Julgue apenas com o texto fornecido, sem conhecimento
externo.

Responda em JSON com exatamente estas chaves, nesta ordem:
- "reasoning": 2 a 4 frases com a sua análise. Escreva esta chave antes de decidir as demais.
- "answerable": "yes" somente se o texto do ARTIGO, sozinho, contém a resposta completa à pergunta;
  "partial" se contém só parte da resposta ou depende de outro dispositivo; "no" se não contém a resposta.
- "also_answered_by": lista com os rótulos, como "C2", dos ARTIGOS CONCORRENTES cujo texto, sozinho, contém
  a resposta completa à pergunta. Tratar de tema parecido não conta. Lista vazia se nenhum contém. Use apenas
  rótulos listados abaixo.
- "leakage": "heavy" se a pergunta reproduz uma frase do ARTIGO ou cita artigo, dispositivo, parágrafo, inciso
  ou lei; "some" se reaproveita termos técnicos distintivos do ARTIGO numa pergunta que soa natural; "none"
  nos demais casos.
- "category": "procedimento" se a pergunta pede como fazer algo, etapas, requisitos ou condições de validade
  de um ato; "fato_pontual" se a resposta é um valor, prazo, número, parte ou fato único; "conceito" se a
  pergunta pede uma definição. Na dúvida entre "procedimento" e "fato_pontual", use "procedimento" quando a
  resposta descreve condições ou requisitos, e "fato_pontual" quando é um único dado.

PERGUNTA:
{question}

ARTIGO {header}:
{article}

ARTIGOS CONCORRENTES:
{competitors}
"""


def openai_judge_v2(client, question: str, header: str, article: str, competitors: list[dict],
                    corpus: dict[str, str]) -> JudgeVerdict:
    return judge(client, question, header, article, competitors, corpus, prompt=RUBRIC_V2)


def anthropic_judge(client, question: str, header: str, article: str, competitors: list[dict],
                    corpus: dict[str, str]) -> JudgeVerdict:
    labels = {c["label"] for c in competitors}
    content = RUBRIC_V2.format(question=question, header=header, article=article,
                               competitors=competitor_block(competitors, corpus))
    last_error = ""
    for _ in range(MAX_JUDGE_ATTEMPTS):
        # As on the OpenAI path, only a bad model output is a failed attempt. anthropic transport and API errors
        # are not ValueError, so they propagate: the run stops, no row is written, and a rerun judges again.
        try:
            # anthropic 1.x removed sampling parameters from its signatures, but the API still honours them for
            # Haiku 4.5, and the spec requires temperature 0, so it goes in extra_body.
            response = client.messages.parse(
                model=ANTHROPIC_JUDGE_MODEL, max_tokens=ANTHROPIC_MAX_TOKENS,
                messages=[{"role": "user", "content": content}], output_format=JudgeVerdict,
                extra_body={"temperature": 0})
        except ValueError as exc:  # the parsed output failed JudgeVerdict validation
            last_error = str(exc)
            continue
        if response.stop_reason != "end_turn":
            last_error = f"stop_reason {response.stop_reason}"
            continue
        verdict = response.parsed_output
        if not isinstance(verdict, JudgeVerdict):
            last_error = "response carried no parsed verdict"
            continue
        unknown = sorted(set(verdict.also_answered_by) - labels)
        if unknown:
            last_error = f"unknown competitor labels {unknown}"
            continue
        return verdict
    raise JudgeError(f"{ANTHROPIC_JUDGE_MODEL} failed after {MAX_JUDGE_ATTEMPTS} attempts: {last_error}")


JUDGES = {OPENAI_JUDGE_MODEL: openai_judge_v2, ANTHROPIC_JUDGE_MODEL: anthropic_judge}


def run_judgments(candidates: list[dict], triage: dict[str, dict], corpus: dict[str, str], clients: dict,
                  out_path: Path, limit: int | None = None) -> dict:
    missing = [model for model in JUDGES if model not in clients]
    if missing:
        raise ValueError(f"missing clients for {missing}")
    done: set[str] = set()
    if out_path.exists():
        drop_malformed_tail(out_path)
        done = {row["candidate_id"] for row in read_jsonl_rows(out_path)}
    by_id = {c["candidate_id"]: c for c in candidates}
    todo = [cid for cid in sorted(triage) if triage[cid]["status"] != "refused" and cid not in done]
    counts = {"judged_rows": 0, "judge_errors": 0, "already_in_file": len(done)}
    if limit is not None:
        todo = todo[:limit]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for cid in todo:
        cand, triage_row = by_id[cid], triage[cid]
        error = validate_candidate(cand, corpus)
        if error:
            raise ValueError(f"{cid}: {error}; triage already refuses bad spans, so the inputs changed")
        article = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
        judges = {}
        for model, judge_fn in JUDGES.items():
            try:
                verdict = judge_fn(clients[model], cand["question"], cand["header"], article,
                                   triage_row["competitors"], corpus)
                judges[model] = {"verdict": verdict.model_dump(), "error": None}
            except JudgeError as exc:
                judges[model] = {"verdict": None, "error": str(exc)}
                counts["judge_errors"] += 1
        row = {"candidate_id": cid, "rubric_version": RUBRIC_VERSION, "judged_at": dt.date.today().isoformat(),
               "judges": judges}
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        counts["judged_rows"] += 1
    return counts


def main(smoke: bool, limit: int | None) -> None:
    import anthropic
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    triage = load_triage(TRIAGE)
    if not triage:
        sys.exit(f"no triage rows in {TRIAGE}; run evals.groundtruth.golden.triage first")
    corpus, candidates = load_corpus(), load_candidates()
    clients = {OPENAI_JUDGE_MODEL: OpenAI(), ANTHROPIC_JUDGE_MODEL: anthropic.Anthropic()}
    if smoke:
        cid = next(c for c in sorted(triage) if triage[c]["status"] != "refused")
        cand = {c["candidate_id"]: c for c in candidates}[cid]
        article = corpus[cand["doc_id"]][cand["start"]:cand["end"]]
        for model, judge_fn in JUDGES.items():
            verdict = judge_fn(clients[model], cand["question"], cand["header"], article,
                               triage[cid]["competitors"], corpus)
            print(model, verdict.model_dump_json(indent=2))
        return
    print(json.dumps(run_judgments(candidates, triage, corpus, clients, JUDGMENTS, limit=limit)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="one call per judge on the first candidate, no file written")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    main(args.smoke, args.limit)
