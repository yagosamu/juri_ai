# Abstention and over-refusal

What this file measures, and why it exists. Task 20 told the agent to say plainly that it found no
basis in the knowledge base instead of answering from general knowledge, and the 2026-10-06
generation run abstained on 10 of 10 out-of-scope questions. The same instruction created a failure
mode in the other direction: one in-scope golden question, `r1-cdc-060`, was refused although the
base covers it. The two metrics this project publishes, DeepEval faithfulness and answer relevancy,
cannot see that, because a refusal asserts nothing and so contradicts nothing. This file measures
both directions with a deterministic, offline detector, and `tests/test_abstention_gate.py` gates
both counts.

Source: the committed `generation/answers.jsonl` and `generation/scores.json` of the 2026-10-06 run,
the same two files `results/generation.md` was rendered from. Detector:
`generation/refusal.py`, which matches a small set of explicit phrasings on normalized text, with no
model call, no length threshold and no score anywhere in the decision. Reproduce the counts with
`python -m evals.groundtruth.generation.refusal`, which needs no API key.

## The two counts

| direction | metric | count | n | baseline | tolerance |
|---|---|---|---|---|---|
| out of scope | answers detected as an abstention | 10 | 10 | 10 | may not fall at all |
| in scope | golden answers detected as a refusal | 1 | 30 | 1 | may not rise at all |

The baseline is `generation/abstention_baseline.json`, taken from this run. Both tolerances are
exact: these are integer counts read from one committed file, so the same file gives the same two
integers on every run and there is no measurement noise for a tolerance to absorb. One row is also a
large step at this n, 10 percentage points out of 10 rows and 3.3 out of 30.

## Every row the detector flagged

| id | in scope | phrasing that matched | matched span |
|---|---|---|---|
| r1-cdc-060 | yes | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |
| oos-01 | no | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |
| oos-02 | no | no_information_in_base | nao encontrei informacoes na base de conhecimento |
| oos-03 | no | no_information_in_base | nao encontrei informacoes na base de conhecimento |
| oos-04 | no | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |
| oos-05 | no | no_information_in_base | nao encontrei informacoes na base de conhecimento |
| oos-06 | no | no_information_in_base | nao encontrei informacoes na base de conhecimento |
| oos-07 | no | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |
| oos-08 | no | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |
| oos-09 | no | no_information_in_base | nao encontrei informacoes na base de conhecimento |
| oos-10 | no | no_information_in_base | nao encontrei informacoes especificas na base de conhecimento |

The matched span is the normalized text, casefolded and with accents stripped, so a reader can see
exactly which words carried the verdict. Every row of this run matched the same phrasing,
`no_information_in_base`. The other two phrasings the detector knows, `no_basis_pinned` and
`no_information_in_documents`, matched nothing here; the first is the sentence
`JuriAI.INSTRUCTIONS` asks for, and the second is the documents wording of the same sentence.

## Agreement with the two judges

The 10 out-of-scope rows carry a two-judge label in `scores.json`, from the rubric in
`generation/abstention.py`: `abstained` only when both gpt-4.1 and claude-haiku-4-5 say the answer
gave no substantive response. All 10 are labelled `abstained`.

**The detector agrees with the judge label on 10 of 10 rows. There is no disagreement to name.**

Two cautions about that number. It is agreement on the easy side of the distribution: all 10 rows
are abstentions under both methods, so this run contains no row where a refusal was phrased in a way
the judges accepted and the detector missed, which is the case the agreement would need to rule out.
And the judges are the reference here, not the detector: the rubric in `generation/abstention.py`
remains the measurement of out-of-scope abstention, and the detector is a cheap offline guard beside
it.

One artifact note for a future reader. `scores.json` carries top-level aggregate keys beside its
per-row lists. Nothing reads them: both `run_report_only`, which rendered the committed
`results/generation.md`, and this file compute from the per-row data. They were left stale by the
rerun of the four rate-limited rows, reading 8 abstained and 2 run_failed while the per-row labels
said 10 and 0, so `merge_scores` now recomputes every aggregate the payload carries, and the
committed file was refreshed the same way. Re-rendering `results/generation.md` afterwards produced
the identical file, which is the evidence that no published number came from those keys.

## r1-cdc-060, the refusal the published means reward

`r1-cdc-060` is a golden question, in scope. The agent searched the knowledge base, retrieved 1
context, and still answered:

> Não encontrei informações específicas na base de conhecimento sobre o que pode ser feito se
> ninguém se habilitar para receber a indenização dentro de um ano, considerando a gravidade do dano.

Its scores in `generation/scores.json`: **faithfulness 1.0 and relevancy 1.0**. A refusal asserts
nothing, so there is nothing in it for the faithfulness judge to find unsupported by the retrieved
context, and nothing for the relevancy judge to find off topic. Both judges give it a perfect score,
so an over-refusing agent raises both published means instead of lowering them. Measured on this
run:

| metric | published, with r1-cdc-060 | without r1-cdc-060 |
|---|---|---|
| faithfulness | 0.9381279434850863 over n=28 | 0.9358363858363858 over n=27 |
| relevancy | 0.9713247863247862 over n=30 | 0.9703359858532272 over n=29 |

So the refused row lifts the published faithfulness mean by 0.002291557648700482 and the relevancy
mean by 0.000988800471559026. The direction is the point, not the size: every further refusal of an
in-scope question would push both means up again, and no number in `results/generation.md` would
fall. That is why the in-scope count is gated separately.

## Before and after

The pre-adoption run is preserved in `generation/answers_pre_adoption.jsonl` and
`generation/scores_pre_adoption.json`, measured under the 5000/0 chunking and with no abstention
instruction. The same detector, over both runs:

| run | out-of-scope abstentions detected | of n | golden refusals detected | of n | out-of-scope failed runs |
|---|---|---|---|---|---|
| pre-adoption | 0 | 10 | 0 | 30 | 3 |
| 2026-10-06 | 10 | 10 | 1 | 30 | 0 |

Both directions moved together: the instruction bought 10 out-of-scope abstentions and cost 1
in-scope refusal. The chunking changed in the same step, so neither number isolates the instruction;
`results/generation_adoption.md` records that confound.

The 3 pre-adoption out-of-scope rows that failed on a rate limit (oos-01, oos-07, oos-08) are not
counted as abstentions: the detector treats a failed run as never a refusal, because its answer
field holds the error text agno put there, not something the agent chose to say. On those three rows
the stored judge labels (`answered`, `disagreement`, `disagreement`) were produced from that error
text, which is why the pre-adoption agreement of 10 of 10 is weaker evidence than it looks.

## What this metric does not see

It matches known phrasings, so it can undercount. A refusal worded some way the detector does not
carry, for instance one that says the documents do not address the question without using any of
the three phrasings, is counted as an answer, and both numbers above are floors rather than
measurements: the out-of-scope count can only be too low, and the in-scope count can only be too
low, which is the direction that hides over-refusal. It also cannot see a partial refusal: an answer
that carries one of these phrasings and then gives the rule, the deadline or the article anyway is
counted here as a refusal, because the decision is the phrasing and nothing else. It does not judge
whether a refusal was correct, only that it happened, so a correct abstention on an in-scope
question whose passage the base genuinely lacks would still count against the in-scope number. And
it reads a committed artifact rather than live behaviour: both counts come from the answers recorded
on 2026-10-06, so editing `JuriAI.INSTRUCTIONS` changes nothing here until the generation run is
rerun, which costs money, and re-recorded. There is no human legal review of any row in this file.
