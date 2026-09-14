# Golden set by judge consensus

Judges: gpt-4.1, claude-haiku-4-5. Rubric v2. No human legal review.

Candidates: 80. Included: 59. Excluded: 21.

## Exclusion reasons

A candidate can have more than one reason.

| reason | candidates |
|---|---|
| also_answered_by | 16 |
| answerable | 4 |
| category_no_majority | 4 |
| cites_source | 1 |
| judge_missing | 2 |

## Golden set

| category | items |
|---|---|
| conceito | 11 |
| fato_pontual | 18 |
| procedimento | 30 |

No-leakage subset: 20 of 59 items, where no judge rated leakage heavy and the longest copied run is under 5 tokens.

## Agreement between judges

| field | n | agreement | Cohen's kappa |
|---|---|---|---|
| answerable | 78 | 0.962 | 0.381 |
| also answered by any | 78 | 0.833 | 0.199 |
| leakage | 78 | 0.282 | -0.077 |
| category | 78 | 0.692 | 0.468 |

Both judges are language models, one of them a smaller model; each saw truncated competitor previews, and a competitor the triage did not surface remains possible.
