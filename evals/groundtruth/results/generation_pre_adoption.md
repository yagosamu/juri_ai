# Generation report

## Setup

Agent model: gpt-4o (agno default, JuriAI.build_agent sets no model).
Retrieval config: production (5000/0 dense, ia/retrieval_config.py).
Sample: seed 7, 30 golden questions.
Sampled golden ids: r1-clt-045, r1-clt-031, r1-clt-051, r1-cpc-015, r1-cdc-062, r1-cdc-063, r1-lgpd-071, r1-cpc-008, r1-cdc-067, r1-clt-048, r1-cpc-011, r1-lgpd-073, r1-cpc-004, r1-clt-038, r1-cdc-060, r1-cdc-066, r1-clt-054, r1-clt-053, r1-lgpd-072, r1-clt-040, r1-cpc-018, r1-cpc-009, r1-cpc-016, r1-cpc-025, r1-cdc-069, r1-clt-039, r1-cpc-026, r1-lgpd-077, r1-cdc-059, r1-cpc-029.
Out-of-scope ids: oos-01, oos-02, oos-03, oos-04, oos-05, oos-06, oos-07, oos-08, oos-09, oos-10.
Memory is isolated per question: each question starts with an empty agno memory file.
DeepEval judge model: gpt-4.1-mini, deepeval version 3.9.9.
Abstention judges: gpt-4.1, claude-haiku-4-5.

## Faithfulness and relevancy

| category | faithfulness mean | faithfulness n | relevancy mean | relevancy n |
|---|---|---|---|---|
| conceito | 0.959 | 7 | 0.972 | 8 |
| fato_pontual | 0.969 | 8 | 1.000 | 8 |
| procedimento | 0.939 | 14 | 0.980 | 14 |
| overall | 0.952 | 29 | 0.983 | 30 |

No retrieval, excluded from the faithfulness mean: 1.
Run failed, excluded from both means: 0.
No golden run failed, so faithfulness and relevancy are unchanged from the run that produced these scores.

## Abstention

Abstained: 0 of 7 completed runs.
Answered: 7 of 7 completed runs.
Disagreement: 0 of 7 completed runs.
Unverified: 0 of 7 completed runs.
Run failed: 3 of 10 out-of-scope questions.

| id | question | label |
|---|---|---|
| oos-01 | Qual é a pena prevista para o crime de estelionato? | run_failed |
| oos-02 | Com quantos pontos na carteira de habilitação o motorista tem o direito de dirigir suspenso? | answered |
| oos-03 | Até quando a pessoa física precisa entregar a declaração anual do Imposto de Renda? | answered |
| oos-04 | Quem herda primeiro quando alguém morre sem deixar testamento? | answered |
| oos-05 | Qual é o prazo de validade do passaporte comum brasileiro? | answered |
| oos-06 | Qual é a idade mínima para se candidatar a presidente da República? | answered |
| oos-07 | Qual é o valor da multa para quem não vota nas eleições? | run_failed |
| oos-08 | Qual é a pena para quem desmata área de preservação permanente? | run_failed |
| oos-09 | O condomínio pode proibir que moradores tenham animais de estimação? | answered |
| oos-10 | Quais documentos são necessários para registrar uma marca no INPI? | answered |

## Failed runs

3 run(s) exceeded the account's gpt-4o tokens-per-minute (TPM) limit and returned OpenAI's rate-limit error instead of an answer.

| id | limit | requested |
|---|---|---|
| oos-01 | 30000 | 40540 |
| oos-07 | 30000 | 40571 |
| oos-08 | 30000 | 39229 |

A single agent turn with the production retrieval config (5000-character chunks, 10 results per search) can send enough context to gpt-4o to exceed a Tier 1 OpenAI account's 30,000 tokens-per-minute limit on its own.

## Tool use

Answers that searched the knowledge base: 36 of 40.
Answers that called DataJud: 0 of 40.

## Measured cost per model

| model | input tokens | output tokens | cost (USD) |
|---|---|---|---|
| gpt-4o | 555156 | 8986 | 1.4778 |
| gpt-4.1 | 3258 | 801 | 0.0129 |
| claude-haiku-4-5 | 6322 | 1282 | 0.0127 |
| gpt-4.1-mini (cost reported by the tool, not tokens times price) | n/a | n/a | 0.3701 |
| total | | | 1.8735 |

Price source: gpt-4o, gpt-4.1-mini and gpt-4.1: developers.openai.com model page. claude-haiku-4-5: platform.claude.com pricing page. text-embedding-3-small: fetched 2026-09-14. Recorded by the controller on 2026-09-15.

Measured cost excludes agno's background memory-update calls (update_memory_on_run=True): one call per question, using gpt-4o through MemoryManager.create_user_memories, input limited to the question plus agno's own memory prompt. Their usage is never merged into run.metrics, so it is not measured here.

Judge usage above includes calls made on failed runs' error text: those calls were real, paid calls, even though the verdict they returned is never used for a label or a count.

## Limitations

- Both scorers are LLM judges: DeepEval faithfulness/relevancy and the two-judge abstention rubric.
- There is no human legal review of any score in this report.
- 30 golden questions is a sample, drawn with random.Random(7).sample; it is not the full golden set.
- The agent's instructions do not ask it to abstain on an out-of-scope question, only to say when it is unsure; abstention is measured as production behaves, not as a requirement.
- gpt-4o output varies between runs, and nothing here was averaged over repeated runs.
- Measured cost excludes agno's background memory-update calls (update_memory_on_run=True): one call per question, using gpt-4o through MemoryManager.create_user_memories, input limited to the question plus agno's own memory prompt. Their usage is never merged into run.metrics, so it is not measured here.

