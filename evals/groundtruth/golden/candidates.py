"""Sample statute articles and ask an LLM for one lawyer-style question per article.

Output: golden/candidates.jsonl. Nothing here is a golden item until a human reviews it.
Usage: .venv/Scripts/python.exe -m evals.groundtruth.golden.candidates [--round 1] [--force]
"""
import argparse
import json
import random
import sys

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, field_validator

from evals.groundtruth.config import CANDIDATES, load_corpus
from evals.groundtruth.golden.articles import split_articles
from evals.groundtruth.golden.schema import Category

QUOTA = {"cpc": 30, "clt": 25, "cdc": 15, "lgpd": 10}
MIN_CHARS, MAX_CHARS = 200, 3000
MODEL = "gpt-4.1-mini"
PROMPT = """Você recebe um artigo de lei brasileira. Escreva UMA pergunta que um advogado faria
a um assistente jurídico e cuja resposta está neste artigo. Regras:
- não cite o número do artigo nem o nome da lei na pergunta;
- use linguagem natural, como numa conversa;
- classifique em: "fato_pontual" (prazo, valor, número, quem), "conceito" (definição, o que é),
  "procedimento" (como fazer, etapas, requisitos).
Responda em JSON: {"question": "...", "category": "..."}.

ARTIGO:
"""


class ModelAnswer(BaseModel):
    """The only fields trusted from a model response.

    Everything else about a candidate (doc_id, start, end, header) comes from our own sampling
    over the corpus and must never be taken from the model: extra keys are rejected outright so a
    response cannot silently overwrite the trusted article metadata a later step slices with.
    """
    model_config = ConfigDict(extra="forbid")

    question: str
    category: Category

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


def sample_articles(corpus: dict[str, str], seed: int) -> list[dict]:
    rng = random.Random(seed)
    picked = []
    for doc_id, quota in QUOTA.items():
        arts = [a for a in split_articles(corpus[doc_id]) if MIN_CHARS <= a.end - a.start <= MAX_CHARS]
        for a in rng.sample(arts, quota):
            picked.append({"doc_id": doc_id, "start": a.start, "end": a.end, "header": a.header})
    return picked


def ask(client: OpenAI, passage: str) -> ModelAnswer:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PROMPT + passage}],
    )
    raw = json.loads(resp.choices[0].message.content)
    return ModelAnswer.model_validate(raw)


def existing_candidate_ids() -> set[str]:
    if not CANDIDATES.exists():
        return set()
    return {json.loads(l)["candidate_id"] for l in CANDIDATES.read_text(encoding="utf-8").splitlines() if l.strip()}


def round_already_generated(round_number: int, existing_ids: set[str]) -> bool:
    prefix = f"r{round_number}-"
    return any(candidate_id.startswith(prefix) for candidate_id in existing_ids)


def main(round_number: int, force: bool = False) -> None:
    load_dotenv()
    corpus = load_corpus()
    if not force and round_already_generated(round_number, existing_candidate_ids()):
        print(f"round {round_number} already has candidates in {CANDIDATES}; pass --force to regenerate")
        return
    client = OpenAI()
    with CANDIDATES.open("a", encoding="utf-8") as out:
        for i, art in enumerate(sample_articles(corpus, seed=42 + round_number)):
            candidate_id = f"r{round_number}-{art['doc_id']}-{i:03d}"
            try:
                answer = ask(client, corpus[art["doc_id"]][art["start"]:art["end"]])
            except ValueError as exc:
                print(f"skip {candidate_id}: invalid model response ({exc})")
                continue
            row = {
                "candidate_id": candidate_id,
                "doc_id": art["doc_id"],
                "start": art["start"],
                "end": art["end"],
                "header": art["header"],
                "question": answer.question,
                "category": answer.category,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(row["candidate_id"], row["category"], row["question"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="regenerate a round even if candidates for it already exist")
    args = parser.parse_args()
    main(args.round, args.force)
