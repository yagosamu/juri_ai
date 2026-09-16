"""Task 9b: runs the real JuriAI agent on the sampled questions, then scores the answers
(brief task-9b-brief.md, Phase 1 and Phase 2).

Nothing at module import time touches Django or ia: every side effect (setting env vars, calling
django.setup(), importing ia.agents/ia.tasks, running the agent, calling OpenAI/Anthropic/DeepEval)
happens inside main(), so the pure helpers below can be imported and unit tested without any of it
(brief R2). Usage:
  .venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation --smoke --limit-golden 1 --limit-oos 1
  .venv/Scripts/python.exe -m evals.groundtruth.generation.run_generation
"""
import argparse
import json
import os
import sys
from pathlib import Path

from evals.groundtruth.config import (ANSWERS, GENERATION_REPORT, GENERATION_RUNTIME_DIR, GOLDEN_SET, OUT_OF_SCOPE,
                                      SAMPLE_SEED, SAMPLE_SIZE, SCORES, load_corpus)
from evals.groundtruth.generation.abstention import abstention_counts, relabel_stored_abstention, run_abstention
from evals.groundtruth.generation.answers import build_answer_row, is_failed_run
from evals.groundtruth.generation.cost import PRICE_SOURCE, model_cost, total_cost
from evals.groundtruth.generation.documentos_table import ensure_documentos_table
from evals.groundtruth.generation.gen_report import MEMORY_UPDATE_COST_NOTE, render_report
from evals.groundtruth.generation.guard import assert_runtime_uri
from evals.groundtruth.generation.memory import fresh_memory_path
from evals.groundtruth.generation.scoring import (aggregate_faithfulness_relevancy, reconcile_scored_golden,
                                                  score_golden_answers)
from evals.groundtruth.generation.select import select_questions
from evals.groundtruth.golden.jsonl_io import read_jsonl_rows
from evals.groundtruth.golden.schema import load_golden

AGENT_MODEL = "gpt-4o"  # agno's default when JuriAI.build_agent sets no model (agno/agent/agent.py:803)
DEEPEVAL_MODEL = "gpt-4.1-mini"
OPENAI_ABSTENTION_JUDGE = "gpt-4.1"
ANTHROPIC_ABSTENTION_JUDGE = "claude-haiku-4-5"
ABSTENTION_JUDGES = [OPENAI_ABSTENTION_JUDGE, ANTHROPIC_ABSTENTION_JUDGE]
RETRIEVAL_CONFIG_LABEL = "production (5000/0 dense, ia/retrieval_config.py)"
DOCUMENTOS_EXPECTED_COUNT = 285
TENANT = 0  # single public tenant; mirrors evals.groundtruth.indexer.TENANT and cliente_id metadata
OUT_OF_SCOPE_CATEGORY = "fora_de_escopo"  # matches generation/out_of_scope_check.py's REQUIRED_KEYS check


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-golden", type=int, default=None, help="cap how many golden questions run")
    parser.add_argument("--limit-oos", type=int, default=None, help="cap how many out-of-scope questions run")
    parser.add_argument("--smoke", action="store_true",
                        help="write answers and scores only under evals/groundtruth/runtime/generation")
    parser.add_argument("--report-only", action="store_true",
                        help="rebuild results/generation.md from generation/answers.jsonl and "
                             "generation/scores.json only; makes no model, embedding or judge call")
    parser.add_argument("--only", nargs="+", default=None, metavar="ID",
                        help="rerun only these ids; refuses any id that is not currently a failed run")
    return parser


def partition_selected(selected: list[dict]) -> tuple[list[dict], list[dict]]:
    golden = [item for item in selected if item["kind"] == "golden"]
    out_of_scope = [item for item in selected if item["kind"] == "out_of_scope"]
    return golden, out_of_scope


def apply_limits(golden_items: list[dict], oos_items: list[dict], limit_golden, limit_oos
                 ) -> tuple[list[dict], list[dict]]:
    if limit_golden is not None:
        golden_items = golden_items[:limit_golden]
    if limit_oos is not None:
        oos_items = oos_items[:limit_oos]
    return golden_items, oos_items


def tool_use_summary(rows: list[dict]) -> dict:
    return {"searched": sum(1 for r in rows if r["searched"]),
           "datajud_called": sum(1 for r in rows if r["datajud_called"]), "total": len(rows)}


def usage_total(rows: list[dict]) -> dict:
    """Sums the agent's own input/output tokens (row["usage"]) across a list of answer rows, plus any
    prior_usage an answer row carries forward from an attempt --only replaced (fix round 2 ruling: Part 2
    keeps earlier spend), so replacing a row's answer never silently drops tokens already paid for."""
    input_tokens = sum(r["usage"]["input_tokens"] for r in rows)
    output_tokens = sum(r["usage"]["output_tokens"] for r in rows)
    for r in rows:
        for prior in r.get("prior_usage", []):
            input_tokens += prior.get("input_tokens", 0)
            output_tokens += prior.get("output_tokens", 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def abstention_judge_usage(results: list[dict], judge_model: str) -> dict:
    """Sums one judge's input/output tokens across abstention results, plus that judge's share of any
    prior_attempts an item carries forward from a replaced attempt (fix round 2 ruling). A failed run's
    result still carries its own stored judges usage (owner resolution: the judge call on the error text
    was real, paid spend, even though its verdict is never used for a label or a count), so it is summed
    here exactly like a completed row's usage, with no special case needed.
    """
    input_tokens, output_tokens = 0, 0
    for r in results:
        usage = r["judges"].get(judge_model, {}).get("usage")
        if usage:
            input_tokens += usage["input_tokens"]
            output_tokens += usage["output_tokens"]
        for prior in r.get("prior_attempts", []):
            prior_usage = (prior.get("judges_usage") or {}).get(judge_model)
            if prior_usage:
                input_tokens += prior_usage.get("input_tokens", 0)
                output_tokens += prior_usage.get("output_tokens", 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def deepeval_cost_total(scored_golden: list[dict]) -> float:
    """Sums DeepEval's own evaluation_cost across every measured relevancy and faithfulness call, plus
    the deepeval_cost of any prior_attempts an item carries forward from a replaced attempt (fix round 2
    ruling: Part 2 keeps earlier spend).

    DeepEval does not expose the raw prompt/completion token counts per metric through its public
    API, only the dollar evaluation_cost it computes itself from those tokens and its own internal
    price table, so this is reported separately from the tokens times recorded price rows.
    """
    total = 0.0
    for row in scored_golden:
        total += row.get("relevancy_cost") or 0.0
        total += row.get("faithfulness_cost") or 0.0
        for prior in row.get("prior_attempts", []):
            total += prior.get("deepeval_cost") or 0.0
    return total


def build_limitations() -> list[str]:
    """The fixed R7 limitations list, including the unmetered agno memory-update cost note verbatim so the
    cost section and this section state it identically."""
    return [
        "Both scorers are LLM judges: DeepEval faithfulness/relevancy and the two-judge abstention rubric.",
        "There is no human legal review of any score in this report.",
        "30 golden questions is a sample, drawn with random.Random(7).sample; it is not the full golden set.",
        "The agent's instructions do not ask it to abstain on an out-of-scope question, only to say when it "
        "is unsure; abstention is measured as production behaves, not as a requirement.",
        "gpt-4o output varies between runs, and nothing here was averaged over repeated runs.",
        MEMORY_UPDATE_COST_NOTE,
    ]


def failed_rows_of(rows: list[dict]) -> list[dict]:
    return [r for r in rows if is_failed_run(r)]


def split_by_kind(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """An answers.jsonl row list split into (golden_rows, oos_rows) by its category field."""
    golden_rows = [r for r in rows if r["category"] != OUT_OF_SCOPE_CATEGORY]
    oos_rows = [r for r in rows if r["category"] == OUT_OF_SCOPE_CATEGORY]
    return golden_rows, oos_rows


def select_only_ids(all_rows: list[dict], only_ids: list[str]) -> list[dict]:
    """The rows named by only_ids, in the given order. Refuses (ValueError) any id that is not found or
    is not currently a failed run, so a real answer can never be redrawn by --only."""
    by_id = {r["id"]: r for r in all_rows}
    selected = []
    for rid in only_ids:
        row = by_id.get(rid)
        if row is None:
            raise ValueError(f"{rid}: not found in generation/answers.jsonl")
        if not is_failed_run(row):
            raise ValueError(f"{rid}: is not currently a failed run, refusing to rerun a real answer")
        selected.append(row)
    return selected


def replace_rows(all_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """all_rows with every row whose id matches a row in new_rows replaced by that new row, in place of
    the original position; a new_rows id absent from all_rows is appended at the end.

    Fix round 2 ruling: Part 2 keeps earlier spend. That earlier spend has two parts, both carried onto
    the replacement's prior_usage (fix round 3 finding B): the replaced row's own prior_usage entries,
    from attempts an earlier rerun already replaced, are always carried forward; the replaced row's own
    current usage is appended on top, but only when it is non-zero (the current --only refuses to touch
    anything but a failed row, whose gpt-4o usage is 0, but this stays correct if that ever changes). A
    failed rerun's zero usage must never make an earlier, since-replaced attempt's usage disappear: a
    later cost computation (usage_total) would otherwise silently drop tokens an old attempt already paid
    for, and no attempt's usage is ever counted more than once, either as a row's current usage or as one
    prior_usage entry.
    """
    new_by_id = {r["id"]: r for r in new_rows}
    replaced_ids = set()
    result = []
    for row in all_rows:
        if row["id"] in new_by_id:
            new_row = new_by_id[row["id"]]
            old_usage = row.get("usage")
            prior_usage = list(row.get("prior_usage", []))
            if old_usage and (old_usage.get("input_tokens") or old_usage.get("output_tokens")):
                prior_usage.append(old_usage)
            if prior_usage:
                new_row = {**new_row, "prior_usage": prior_usage}
            result.append(new_row)
            replaced_ids.add(row["id"])
        else:
            result.append(row)
    for row in new_rows:
        if row["id"] not in replaced_ids:
            result.append(row)
    return result


def _golden_spend(item: dict) -> dict:
    return {"deepeval_cost": (item.get("relevancy_cost") or 0.0) + (item.get("faithfulness_cost") or 0.0)}


def _abstention_spend(item: dict) -> dict:
    return {"judges_usage": {model: info["usage"] for model, info in item.get("judges", {}).items()
                             if info.get("usage")}}


def merge_scores(stored: dict, new_golden_scores: list[dict], new_abstention_results: list[dict]) -> dict:
    """stored (an existing scores.json payload) with new_golden_scores and new_abstention_results merged
    in by id, replacing any existing entry for that id and keeping everything else unchanged.

    Fix round 2 ruling: Part 2 keeps earlier spend. When an id being merged in already had a stored item,
    the replacement carries that old item's prior_attempts forward, plus the old item's own spend (its
    deepeval_cost for a golden item, or its per-judge usage for an abstention item) as one more entry,
    appended only when that spend is non-zero (fix round 3). Replacing a score item never drops money
    already paid, and an attempt that made no paid call adds no entry.
    """
    golden_by_id = {s["id"]: s for s in stored.get("golden", [])}
    for s in new_golden_scores:
        old = golden_by_id.get(s["id"])
        if old is not None:
            spend = _golden_spend(old)
            prior = [*old.get("prior_attempts", []), *([spend] if spend["deepeval_cost"] else [])]
            if prior:
                s = {**s, "prior_attempts": prior}
        golden_by_id[s["id"]] = s
    abstention_by_id = {a["id"]: a for a in stored.get("abstention", [])}
    for a in new_abstention_results:
        old = abstention_by_id.get(a["id"])
        if old is not None:
            spend = _abstention_spend(old)
            paid = any(u.get("input_tokens") or u.get("output_tokens") for u in spend["judges_usage"].values())
            prior = [*old.get("prior_attempts", []), *([spend] if paid else [])]
            if prior:
                a = {**a, "prior_attempts": prior}
        abstention_by_id[a["id"]] = a
    return {**stored, "golden": list(golden_by_id.values()), "abstention": list(abstention_by_id.values())}


def _atomic_write_text(path: Path, text: str) -> None:
    """Writes text to path through a temp file in the same directory plus os.replace (fix round 2 ruling
    2a): a crash mid-write leaves a stray .tmp file, never a truncated or missing path, and os.replace
    is a single filesystem rename, so a reader always sees either the old content or the new content,
    never a partial file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(rows: list[dict], path: Path) -> None:
    _atomic_write_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def write_json_atomic(payload: dict, path: Path) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def configure_environment(runtime_dir: Path) -> None:
    """R2 step 1: force the agent's stores into runtime_dir before Django settings load."""
    os.environ["DJANGO_SETTINGS_MODULE"] = os.environ.get("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ["DATA_DIR"] = str(runtime_dir)
    os.environ["LANCEDB_URI"] = str(runtime_dir / "lancedb")
    os.environ["AGNO_MEMORY_DB_FILE"] = str(runtime_dir / "agno_memory.sqlite3")
    os.environ.setdefault("SECRET_KEY", "groundtruth-generation-runtime")


def generate_answers(items: list[dict], juri_ai, runtime_dir: Path, tenant: int = TENANT) -> list[dict]:
    """Runs the real agent once per item, with a fresh, empty memory file set before each run (R2).

    juri_ai.MEMORY_DB_FILE is a class attribute that build_agent reads on every call, so setting it
    before each build_agent() call isolates that question's memory from every other question.
    """
    rows = []
    for item in items:
        juri_ai.MEMORY_DB_FILE = str(fresh_memory_path(runtime_dir, item["id"]))
        agent = juri_ai.build_agent(knowledge_filters={"cliente_id": tenant})
        run = agent.run(item["question"])
        rows.append(build_answer_row(item, run))
    return rows


def run_report_only() -> dict:
    """Fix round 1 Part 1, revised by fix round 2 ruling 1: rebuilds results/generation.md from
    generation/answers.jsonl and generation/scores.json only. Makes no model, embedding or judge call,
    so it works with empty OPENAI_API_KEY / ANTHROPIC_API_KEY. Never touches Django or ia.

    Ruling 1: nothing here reads a stored aggregate (scores.json's top-level usage_by_model,
    deepeval_cost_usd, abstention_counts or faithfulness_relevancy). Every rendered number is computed
    from per-row data: gpt-4o tokens from each answers.jsonl row's usage, judge tokens from each
    abstention item's per-judge usage, DeepEval cost as the sum of each golden item's faithfulness_cost
    plus relevancy_cost, and means/n/labels/counts from the per-item scores and verdicts. Those stored
    aggregates may still exist in scores.json as an informational snapshot; nothing here reads them.

    Ruling 2b: reconcile_scored_golden and relabel_stored_abstention each raise (naming the id) if a
    stored item's answer_sha256 does not match the hash of the answer currently in answers.jsonl for
    that id, so a partially-applied --only rerun (new answer, stale score) is caught here rather than
    silently rendered.
    """
    golden_rows, oos_rows = split_by_kind(read_jsonl_rows(ANSWERS))
    stored = json.loads(SCORES.read_text(encoding="utf-8"))

    scored_golden = reconcile_scored_golden(golden_rows, stored["golden"])
    agg = aggregate_faithfulness_relevancy(scored_golden)

    abstention_results = relabel_stored_abstention(oos_rows, stored["abstention"])
    counts = abstention_counts(abstention_results)

    all_rows = golden_rows + oos_rows
    tool_use = tool_use_summary(all_rows)
    failed = failed_rows_of(all_rows)

    setup = {"agent_model": f"{AGENT_MODEL} (agno default, JuriAI.build_agent sets no model)",
             "retrieval_config": RETRIEVAL_CONFIG_LABEL, "seed": SAMPLE_SEED,
             "sampled_golden_ids": [r["id"] for r in golden_rows], "sampled_oos_ids": [r["id"] for r in oos_rows],
             "deepeval_model": DEEPEVAL_MODEL, "deepeval_version": _deepeval_version(),
             "abstention_judges": ABSTENTION_JUDGES}
    limitations = build_limitations()

    # Recomputed from per-row data (ruling 1), never read from stored["usage_by_model"] / ["deepeval_cost_usd"].
    usage_by_model = {
        AGENT_MODEL: usage_total(all_rows),
        OPENAI_ABSTENTION_JUDGE: abstention_judge_usage(abstention_results, OPENAI_ABSTENTION_JUDGE),
        ANTHROPIC_ABSTENTION_JUDGE: abstention_judge_usage(abstention_results, ANTHROPIC_ABSTENTION_JUDGE),
    }
    extra_costs = {DEEPEVAL_MODEL: deepeval_cost_total(scored_golden)}

    report_text = render_report(setup, agg, abstention_results, counts, tool_use, usage_by_model, PRICE_SOURCE,
                                limitations, extra_costs=extra_costs, failed_rows=failed)
    GENERATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    GENERATION_REPORT.write_text(report_text, encoding="utf-8")

    return {"faithfulness_relevancy": agg, "abstention_results": abstention_results, "abstention_counts": counts,
           "tool_use": tool_use, "failed_ids": [r["id"] for r in failed], "setup": setup,
           "usage_by_model": usage_by_model, "extra_costs": extra_costs}


def score_and_write_only(all_rows: list[dict], new_rows: list[dict], score_golden_fn=score_golden_answers,
                         abstain_fn=run_abstention, abstention_clients: dict | None = None,
                         deepeval_model: str = DEEPEVAL_MODEL) -> dict:
    """The scoring-and-persisting half of --only (fix round 2 ruling 2a). Scores new_rows entirely in
    memory; only once every score call has succeeded does it write generation/scores.json and
    generation/answers.jsonl, each atomically (temp file plus os.replace), scores.json first and then
    answers.jsonl. If score_golden_fn or abstain_fn raises, nothing is written and both files are left
    exactly as they were, since the exception happens before either write call.
    """
    new_golden_rows, new_oos_rows = split_by_kind(new_rows)
    new_golden_scores = score_golden_fn(new_golden_rows, model=deepeval_model) if new_golden_rows else []
    new_abstention_results = abstain_fn(new_oos_rows, abstention_clients) if new_oos_rows else []

    updated_rows = replace_rows(all_rows, new_rows)
    stored = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else {"golden": [], "abstention": []}
    merged = merge_scores(stored, new_golden_scores, new_abstention_results)

    write_json_atomic(merged, SCORES)
    write_jsonl(updated_rows, ANSWERS)
    return merged


def run_only(only_ids: list[str]) -> dict:
    """Fix round 1 Part 2 (not run yet: needs the owner's Tier 2 account). Reruns only only_ids, each of
    which must currently be a failed run (select_only_ids refuses anything else), scores the new rows
    (score_and_write_only, ruling 2a), and re-renders results/generation.md. The runtime guard, memory
    isolation and the documentos count check apply exactly as in a normal run.
    """
    runtime_dir = GENERATION_RUNTIME_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)

    configure_environment(runtime_dir)
    from dotenv import load_dotenv
    load_dotenv(override=False)

    import django
    django.setup()
    from ia.agents import JuriAI
    from ia.tasks import build_document_reader

    assert_runtime_uri(JuriAI.knowledge.vector_db.uri, runtime_dir)

    corpus = load_corpus()
    ensure_documentos_table(JuriAI.knowledge, corpus, build_document_reader(), tenant=TENANT,
                            expected_count=DOCUMENTOS_EXPECTED_COUNT)

    all_rows = read_jsonl_rows(ANSWERS)
    to_rerun = select_only_ids(all_rows, only_ids)
    items = [{"id": r["id"], "question": r["question"], "category": r["category"]} for r in to_rerun]

    new_rows = generate_answers(items, JuriAI, runtime_dir)

    import anthropic
    from openai import OpenAI
    clients = {OPENAI_ABSTENTION_JUDGE: OpenAI(), ANTHROPIC_ABSTENTION_JUDGE: anthropic.Anthropic()}
    score_and_write_only(all_rows, new_rows, abstention_clients=clients)

    return run_report_only()


def main(argv: list[str] | None = None) -> dict:
    args = build_arg_parser().parse_args(argv)

    if args.report_only:
        return run_report_only()
    if args.only:
        return run_only(args.only)

    runtime_dir = GENERATION_RUNTIME_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # R2 step 1-2: env vars before Django settings load, then .env without overriding them.
    configure_environment(runtime_dir)
    from dotenv import load_dotenv
    load_dotenv(override=False)

    # R2 step 3-4: django.setup(), then import ia.agents / ia.tasks.
    import django
    django.setup()
    from ia.agents import JuriAI
    from ia.tasks import build_document_reader

    # Mandatory runtime guard (R2): never write into the repository root lancedb/.
    assert_runtime_uri(JuriAI.knowledge.vector_db.uri, runtime_dir)

    corpus = load_corpus()
    n_chunks = ensure_documentos_table(JuriAI.knowledge, corpus, build_document_reader(), tenant=TENANT,
                                       expected_count=DOCUMENTOS_EXPECTED_COUNT)

    golden = load_golden(GOLDEN_SET)
    from evals.groundtruth.generation.out_of_scope_check import load_out_of_scope
    out_of_scope = load_out_of_scope(OUT_OF_SCOPE)
    selected = select_questions(golden, out_of_scope, SAMPLE_SIZE, SAMPLE_SEED)
    golden_items, oos_items = partition_selected(selected)
    golden_items, oos_items = apply_limits(golden_items, oos_items, args.limit_golden, args.limit_oos)

    golden_rows = generate_answers(golden_items, JuriAI, runtime_dir)
    oos_rows = generate_answers(oos_items, JuriAI, runtime_dir)
    all_rows = golden_rows + oos_rows
    failed = failed_rows_of(all_rows)

    answers_path = (runtime_dir / "answers.jsonl") if args.smoke else ANSWERS
    write_jsonl(all_rows, answers_path)

    scored_golden = score_golden_answers(golden_rows, model=DEEPEVAL_MODEL)
    agg = aggregate_faithfulness_relevancy(scored_golden)

    import anthropic
    from openai import OpenAI
    clients = {OPENAI_ABSTENTION_JUDGE: OpenAI(), ANTHROPIC_ABSTENTION_JUDGE: anthropic.Anthropic()}
    abstention_results = run_abstention(oos_rows, clients)
    counts = abstention_counts(abstention_results)

    usage_by_model = {
        AGENT_MODEL: usage_total(all_rows),
        OPENAI_ABSTENTION_JUDGE: abstention_judge_usage(abstention_results, OPENAI_ABSTENTION_JUDGE),
        ANTHROPIC_ABSTENTION_JUDGE: abstention_judge_usage(abstention_results, ANTHROPIC_ABSTENTION_JUDGE),
    }
    extra_costs = {DEEPEVAL_MODEL: deepeval_cost_total(scored_golden)}

    scores_path = (runtime_dir / "scores.json") if args.smoke else SCORES
    scores_payload = {"golden": scored_golden, "faithfulness_relevancy": agg, "abstention": abstention_results,
                      "abstention_counts": counts, "usage_by_model": usage_by_model,
                      "deepeval_cost_usd": extra_costs[DEEPEVAL_MODEL]}
    write_json_atomic(scores_payload, scores_path)

    setup = {"agent_model": f"{AGENT_MODEL} (agno default, JuriAI.build_agent sets no model)",
             "retrieval_config": RETRIEVAL_CONFIG_LABEL, "seed": SAMPLE_SEED,
             "sampled_golden_ids": [i["id"] for i in golden_items], "sampled_oos_ids": [i["id"] for i in oos_items],
             "deepeval_model": DEEPEVAL_MODEL, "deepeval_version": _deepeval_version(),
             "abstention_judges": ABSTENTION_JUDGES}
    tool_use = tool_use_summary(all_rows)
    limitations = build_limitations()

    if not args.smoke:
        report_text = render_report(setup, agg, abstention_results, counts, tool_use, usage_by_model, PRICE_SOURCE,
                                    limitations, extra_costs=extra_costs, failed_rows=failed)
        GENERATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
        GENERATION_REPORT.write_text(report_text, encoding="utf-8")

    return {"n_chunks": n_chunks, "golden_rows": golden_rows, "oos_rows": oos_rows, "scored_golden": scored_golden,
           "faithfulness_relevancy": agg, "abstention_results": abstention_results, "abstention_counts": counts,
           "usage_by_model": usage_by_model, "extra_costs": extra_costs, "tool_use": tool_use, "setup": setup}


def _deepeval_version() -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version("deepeval")
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = main()
    print(json.dumps({
        "n_chunks": result.get("n_chunks"), "tool_use": result["tool_use"],
        "abstention_counts": result["abstention_counts"],
        "faithfulness_relevancy_overall": result["faithfulness_relevancy"]["overall"],
    }))
