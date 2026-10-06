# Generation under the adopted 1500/150 chunking: before and after

Task 20. Before is `results/generation_pre_adoption.md`, the measurement taken under the 5000/0
chunking that production ran until Task 19, with the rows and scores it was computed from preserved in
`generation/answers_pre_adoption.jsonl` and `generation/scores_pre_adoption.json`. After is
`results/generation.md`, rendered from `generation/answers.jsonl` and `generation/scores.json`.

Every number here is copied from those two rendered reports and from the two score files. Nothing is
recomputed by hand.

## Two things changed together, so this is not a controlled comparison

1. **The chunking.** `CHUNK_SIZE` 5000 to 1500 and `CHUNK_OVERLAP` 0 to 150, adopted in Task 19.
2. **The agent's instructions.** `JuriAI.INSTRUCTIONS` gained an abstention rule in Task 20: search
   the knowledge base first, and when the search returns nothing that supports an answer, say so
   plainly instead of answering from general knowledge.

They changed in the same step, so no result below can be attributed to either one alone. In
particular the jump in abstention is what the instruction was written to cause, but shorter chunks
also change what the agent sees before it decides, and nothing here separates the two.

## Faithfulness and relevancy

| category | faithfulness before | n | faithfulness after | n | relevancy before | n | relevancy after | n |
|---|---|---|---|---|---|---|---|---|
| conceito | 0.959 | 7 | 0.960 | 7 | 0.972 | 8 | 0.969 | 8 |
| fato_pontual | 0.969 | 8 | 0.907 | 8 | 1.000 | 8 | 0.954 | 8 |
| procedimento | 0.939 | 14 | 0.946 | 13 | 0.980 | 14 | 0.983 | 14 |
| overall | 0.952 | 29 | 0.938 | 28 | 0.983 | 30 | 0.971 | 30 |

Both scorers are DeepEval with gpt-4.1-mini as the judge, in both runs. Each run is one pass over 30
golden questions with no repeats, and gpt-4o output varies between runs, so a move of this size is not
evidence of a change in quality in either direction.

The faithfulness `n` falls from 29 to 28 for a recorded reason, not a silent one: see the unscored
counts below.

## Rows excluded from a mean, and why

| reason | before | after |
|---|---|---|
| no retrieval, excluded from the faithfulness mean | 1 | 1 |
| run failed, excluded from both means | 0 | 0 |
| not scored by the judge, excluded from the faithfulness mean | 0 | 1 (`content_filter`) |
| not scored by the judge, excluded from the relevancy mean | 0 | 0 |

The no-retrieval row is `r1-cpc-016` in both runs, the question with no antecedent for "esse tipo de
processo", which the agent answers by asking for clarification instead of searching.

The one unscored metric is `r1-clt-045`, where DeepEval's faithfulness call was refused by the content
filter. The agent's answer is fine and its relevancy was scored normally; only the faithfulness call
was refused. Before, a refusal of that kind had no recorded outcome at all, because it aborted the
whole run: that is exactly what happened on the first pass of this measurement, after all 40 answers
had been paid for. It is now recorded per metric and counted in the report.

## Abstention on the 10 out-of-scope questions

| label | before | after |
|---|---|---|
| abstained | 0 of 7 completed | **10 of 10 completed** |
| answered | 7 of 7 completed | 0 of 10 completed |
| disagreement | 0 | 0 |
| unverified | 0 | 0 |
| run failed | 3 of 10 | 0 of 10 |

Judged by gpt-4.1 and claude-haiku-4-5 together, under the rubric in
`generation/abstention.py`, which labels an answer `abstained` only when it says it found no basis in
the documents or in the knowledge base **and** gives no substantive answer. Both judges agreed on all
10.

This is the clearest result of the task. Before, the agent answered every out-of-scope question it
completed, from general knowledge. After, it declined all 10. Answer length moves the same way: the
completed out-of-scope answers had a median of 474 and a maximum of 1675 characters before, and a
median of 294 and a maximum of 378 after, which is the shape of a refusal rather than a shortened
essay.

## Tokens per turn

Input tokens sent by one agent turn, over the completed rows of each run. A failed run records 0
input tokens of its own, because agno returned the rate-limit error instead of a completed turn and
the tokens it asked for are in the error text, so failed rows are left out of both columns.

| | before | after |
|---|---|---|
| turns | 37 | 40 |
| mean | 15004.216216216217 | 5479.75 |
| median | 14096 | 5640.5 |
| max | 40912 | 6257 |
| turns above 30000 | 2 | 0 |

The per-turn context cost falls by about two thirds, which is what 10 chunks of 1500 characters
instead of 10 of 5000 predicts. The maximum matters more than the mean: before, two completed turns
and all three failed ones were at or above the Tier 1 limit of 30,000 gpt-4o tokens per minute, so a
single turn could exhaust the whole per-minute budget by itself. After, the largest turn is 6257, so
no single turn can.

## Failed runs

| | before | after |
|---|---|---|
| failed runs | 3 of 40 | 0 of 40 |
| ids | oos-01, oos-07, oos-08 | none |

**The four rows in the after column were rerun.** The first pass of this measurement failed 4 of 40
runs on transient rate-limit errors: `r1-lgpd-071`, `r1-cpc-026`, `oos-02` and `oos-10`, each with
`Used` plus `Requested` only 111 to 127 tokens over the 30,000 limit and an API retry hint of about
250 ms. They were rerun with `--only`, which refuses any id that is not currently a failed run, so the
other 36 answers could not be touched. The sample was therefore **restored, not reselected**: these
are the same four ids the seed 7 sample drew, answered on a second attempt, not four different
questions chosen after seeing the first result.

### The failure count is a property of the harness, not of the chunking

`generate_answers` calls the agent back to back with no delay and no backoff. Nothing paces a run
against the account's per-minute budget, so a run walks into its own rate limit: 40 turns at about
5500 tokens each is roughly 220,000 tokens pushed through a 30,000-per-minute window as fast as the
API will take them. That is why 4 turns of about 5500 tokens still failed, when 3 turns of about
15,000 failed before.

The two causes are different and should not be conflated. Before, one turn alone could exceed the
whole per-minute budget, which shorter chunks fixed. After, no turn comes close and any remaining
failure is pacing. No pacing was added in this task, so the failed-run count of any future run
remains a property of that pacing and of the account tier.

## Tool use and cost

| | before | after |
|---|---|---|
| answers that searched the knowledge base | 36 of 40 | 39 of 40 |
| answers that called DataJud | 0 of 40 | 0 of 40 |
| measured cost | $1.8735 | $0.8319 |

The search count rises because 3 of the 4 rows that are now answered were failed runs before, and a
failed run never reached the tool. The one answer that still does not search is `r1-cpc-016`.

Cost falls mostly on gpt-4o, $1.4778 to $0.6176, tracking the drop in input tokens per turn. DeepEval
falls from $0.3701 to $0.1930 for the same reason: faithfulness is judged against the retrieved
context, and that context is now a third of the size.

Two honest gaps in the after figure. It excludes agno's background memory-update calls, exactly as
the before figure does, for the reason given in both reports. It also excludes the DeepEval calls made
during the crashed first pass, before the content filter aborted it: those were real, paid calls, but
nothing was written when the run died, so there is no record of them to count. The owner paid somewhat
more than $0.8319 for this measurement.

`generation/scores.json` still carries a stale `deepeval_cost_usd` of 0.177575 from the scoring pass
that ran before the four reruns. The rendered $0.1930 is recomputed from the per-item costs and
ignores that snapshot, which is the behaviour the report is built to have: no rendered number is ever
read from a stored aggregate.

## Did the agent start refusing in-scope questions?

This was the risk of the instruction, and it has to be looked for rather than inferred from the means.
All 30 golden answers were scanned for refusal wording. **One in-scope question was refused:**

- **`r1-cdc-060`** [procedimento] "O que pode ser feito se ninguem se habilitar para receber a
  indenizacao dentro de um ano, considerando a gravidade do dano?" The agent searched, retrieved one
  context, and answered: "Nao encontrei informacoes especificas na base de conhecimento sobre o que
  pode ser feito se ninguem se habilitar para receber a indenizacao dentro de um ano", then suggested
  consulting the legislation or a lawyer. 371 characters.

That is 1 of 30, and it is the behaviour the instruction asks for applied to a question the corpus
does cover. One case is not a rate, and nothing here says whether it would recur.

**The two means cannot detect this.** DeepEval scored that refusal **faithfulness 1.00** ("there are
no contradictions; the actual output fully aligns with the retrieval context") and **relevancy 1.00**
("the response fully addresses the question without any irrelevant information"). A refusal asserts
nothing, so it contradicts nothing and scores perfectly for faithfulness; DeepEval's relevancy judge
also accepted it. Far from showing up as a drop, the refusal **raises** the means it is in:
procedimento faithfulness is 0.946 with it and 0.941 without, and overall faithfulness is 0.938 with
it and 0.936 without.

So the fall in faithfulness is not caused by refusals. The five lowest-scoring rows after are all
substantive answers, 583 to 1212 characters, marked down for over-claiming against their retrieved
context: `r1-cpc-004` at 0.60 ("implying the author can withdraw the action without the defendant's
consent, whereas the context clearly states withdrawal requires it"), `r1-lgpd-071` at 0.71,
`r1-cdc-067` at 0.80, `r1-clt-053` at 0.80, `r1-cpc-029` at 0.83. A plausible mechanism is that a
1500-character chunk often no longer contains the qualifying sentence that a 5000-character chunk did,
so an answer that generalises past the snippet is now judged unfaithful to it. That is a hypothesis
this run does not test, and it would need a controlled comparison of the chunking alone.

## Limitations

- The chunking and the instruction changed together. No result here isolates either.
- Both scorers are LLM judges, and one of them scored a refusal of an answerable question as a
  perfect answer on both metrics. Faithfulness and relevancy do not measure whether the agent
  answered at all.
- There is no human legal review of any score in either run.
- 30 golden questions is a sample drawn with `random.Random(7).sample`, not the full 59-question set.
  Abstention rests on 10 questions.
- One pass each, no repeats, and gpt-4o output varies between runs.
- Four of the 40 after rows are second attempts, after transient rate-limit failures in the first
  pass.
- The harness paces nothing, so a run's failed-run count reflects that pacing and the account tier
  rather than the configuration being measured.
- The corpus is 4 public Brazilian statutes. Production documents are petitions and contracts passed
  through OCR, and nothing here shows the result carries over to them.
