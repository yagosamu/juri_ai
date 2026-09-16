"""R7: renders the committed results/generation.md report from the pipeline's aggregated outputs.

English, factual, no em-dash, no invented number: every figure comes from the caller's inputs.
"""
import re

from evals.groundtruth.generation.cost import model_cost, total_cost

# Matches the OpenAI 429 TPM message: "... on tokens per min (TPM): Limit 30000, Requested 40571. ..."
TPM_ERROR_PATTERN = re.compile(r"Limit\s+(\d+),\s+Requested\s+(\d+)")

TIER_1_TPM_NOTE = (
    "A single agent turn with the production retrieval config (5000-character chunks, 10 results per "
    "search) can send enough context to gpt-4o to exceed a Tier 1 OpenAI account's 30,000 tokens-per-minute "
    "limit on its own.")

# Confirmed in agno 2.4.7 source: with update_memory_on_run=True, each agent.run() starts a background
# future (ThreadPoolExecutor "agno-bg", agent.py:758-760 and 1136) that calls
# MemoryManager.create_user_memories(message=<the user question>) through _make_memories (agent.py:6250-6269),
# using the agent's own model, gpt-4o (agent.py:826-827). Nothing merges that call's usage into run.metrics, so
# it is never captured by usage_total() and is not in the measured cost below. Kept as one constant so the cost
# section and the limitations section state it identically.
MEMORY_UPDATE_COST_NOTE = (
    "Measured cost excludes agno's background memory-update calls (update_memory_on_run=True): one call per "
    "question, using gpt-4o through MemoryManager.create_user_memories, input limited to the question plus "
    "agno's own memory prompt. Their usage is never merged into run.metrics, so it is not measured here.")

# Fix round 2, owner resolution: judge cost is measured spend, so it counts every paid call, including the
# calls made on a failed run's error text; only the verdict from that call is ignored (for labels and counts).
JUDGE_USAGE_INCLUDES_FAILED_NOTE = (
    "Judge usage above includes calls made on failed runs' error text: those calls were real, paid calls, "
    "even though the verdict they returned is never used for a label or a count.")


def _fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def parse_tpm_error(message: str) -> dict | None:
    """{"limit": int, "requested": int} parsed out of an OpenAI TPM rate-limit message, or None when the
    message does not match that shape."""
    match = TPM_ERROR_PATTERN.search(message or "")
    if not match:
        return None
    return {"limit": int(match.group(1)), "requested": int(match.group(2))}


def render_report(setup: dict, agg: dict, abstention_results: list, abstention_counts_: dict, tool_use: dict,
                  usage_by_model: dict, price_source: str, limitations: list, extra_costs: dict | None = None,
                  failed_rows: list | None = None) -> str:
    """setup keys: agent_model, retrieval_config, seed, sampled_golden_ids, sampled_oos_ids,
    deepeval_model, deepeval_version, abstention_judges. tool_use keys: searched, datajud_called, total.

    extra_costs: {model: USD amount} for a model whose token count is not available (DeepEval does not
    expose raw prompt/completion tokens per metric), already computed by that model's own accounting
    rather than tokens times the recorded price. Included in the total and flagged in the table.

    failed_rows (fix round 1): answer rows (golden or out-of-scope) whose agent run errored, each with
    at least id, question and error. Rendered as a "Failed runs" section with the parsed TPM numbers.
    """
    lines = ["# Generation report", ""]

    lines += ["## Setup", ""]
    lines.append(f"Agent model: {setup['agent_model']}.")
    lines.append(f"Retrieval config: {setup['retrieval_config']}.")
    lines.append(f"Sample: seed {setup['seed']}, {len(setup['sampled_golden_ids'])} golden questions.")
    lines.append("Sampled golden ids: " + ", ".join(setup["sampled_golden_ids"]) + ".")
    lines.append("Out-of-scope ids: " + ", ".join(setup["sampled_oos_ids"]) + ".")
    lines.append("Memory is isolated per question: each question starts with an empty agno memory file.")
    lines.append(f"DeepEval judge model: {setup['deepeval_model']}, deepeval version {setup['deepeval_version']}.")
    lines.append("Abstention judges: " + ", ".join(setup["abstention_judges"]) + ".")
    lines.append("")

    lines += ["## Faithfulness and relevancy", ""]
    lines.append("| category | faithfulness mean | faithfulness n | relevancy mean | relevancy n |")
    lines.append("|---|---|---|---|---|")
    for category, values in agg["by_category"].items():
        f, r = values["faithfulness"], values["relevancy"]
        lines.append(f"| {category} | {_fmt(f['mean'])} | {f['n']} | {_fmt(r['mean'])} | {r['n']} |")
    of, orr = agg["overall"]["faithfulness"], agg["overall"]["relevancy"]
    lines.append(f"| overall | {_fmt(of['mean'])} | {of['n']} | {_fmt(orr['mean'])} | {orr['n']} |")
    lines.append("")
    lines.append(f"No retrieval, excluded from the faithfulness mean: {agg['no_retrieval']}.")
    run_failed_golden = agg.get("run_failed", 0)
    lines.append(f"Run failed, excluded from both means: {run_failed_golden}.")
    if run_failed_golden == 0:
        lines.append("No golden run failed, so faithfulness and relevancy are unchanged from the run that "
                     "produced these scores.")
    lines.append("")

    lines += ["## Abstention", ""]
    total_oos = sum(abstention_counts_.values())
    completed_oos = total_oos - abstention_counts_.get("run_failed", 0)
    lines.append(f"Abstained: {abstention_counts_['abstained']} of {completed_oos} completed runs.")
    lines.append(f"Answered: {abstention_counts_['answered']} of {completed_oos} completed runs.")
    lines.append(f"Disagreement: {abstention_counts_['disagreement']} of {completed_oos} completed runs.")
    lines.append(f"Unverified: {abstention_counts_['unverified']} of {completed_oos} completed runs.")
    lines.append(f"Run failed: {abstention_counts_.get('run_failed', 0)} of {total_oos} out-of-scope questions.")
    lines.append("")
    lines.append("| id | question | label |")
    lines.append("|---|---|---|")
    for r in abstention_results:
        lines.append(f"| {r['id']} | {r['question']} | {r['label']} |")
    lines.append("")

    lines += ["## Failed runs", ""]
    if failed_rows:
        lines.append(f"{len(failed_rows)} run(s) exceeded the account's gpt-4o tokens-per-minute (TPM) limit "
                     "and returned OpenAI's rate-limit error instead of an answer.")
        lines.append("")
        lines.append("| id | limit | requested |")
        lines.append("|---|---|---|")
        for row in failed_rows:
            # A row written before fix round 1 has no separate "error" field, only "answer" (which
            # build_answer_row now also copies into "error" for a failed run); fall back to "answer"
            # so a legacy row's TPM numbers are still parsed and shown, not hidden behind "n/a".
            message = row.get("error") or row.get("answer") or ""
            parsed = parse_tpm_error(message)
            limit = parsed["limit"] if parsed else "n/a"
            requested = parsed["requested"] if parsed else "n/a"
            lines.append(f"| {row['id']} | {limit} | {requested} |")
        lines.append("")
        lines.append(TIER_1_TPM_NOTE)
    else:
        lines.append("No run failed.")
    lines.append("")

    lines += ["## Tool use", ""]
    lines.append(f"Answers that searched the knowledge base: {tool_use['searched']} of {tool_use['total']}.")
    lines.append(f"Answers that called DataJud: {tool_use['datajud_called']} of {tool_use['total']}.")
    lines.append("")

    lines += ["## Measured cost per model", ""]
    lines.append("| model | input tokens | output tokens | cost (USD) |")
    lines.append("|---|---|---|---|")
    grand_total = total_cost(usage_by_model)
    for model, usage in usage_by_model.items():
        cost = model_cost(model, usage["input_tokens"], usage["output_tokens"])
        lines.append(f"| {model} | {usage['input_tokens']} | {usage['output_tokens']} | {cost:.4f} |")
    for model, cost in (extra_costs or {}).items():
        grand_total += cost
        lines.append(f"| {model} (cost reported by the tool, not tokens times price) | n/a | n/a | {cost:.4f} |")
    lines.append(f"| total | | | {grand_total:.4f} |")
    lines.append("")
    lines.append(f"Price source: {price_source}")
    lines.append("")
    lines.append(MEMORY_UPDATE_COST_NOTE)
    lines.append("")
    lines.append(JUDGE_USAGE_INCLUDES_FAILED_NOTE)
    lines.append("")

    lines += ["## Limitations", ""]
    for item in limitations:
        lines.append(f"- {item}")
    lines.append("")

    text = "\n".join(lines) + "\n"
    if "—" in text:
        raise ValueError("report text must not contain an em-dash")
    return text
