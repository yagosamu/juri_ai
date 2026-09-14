| config | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 | p50 search ms |
|---|---|---|---|---|---|---|
| production | 0.373 | 0.864 | 0.915 | 0.594 | 0.675 | 12 |

p50 search ms: wall-clock time inside retriever.search with the query embedding already computed, on the machine that ran it; informational, not gated.

no-leakage subset (spec): no judge rated leakage heavy and the longest copied run is under 5 tokens

| config | n | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 |
|---|---|---|---|---|---|---|
| production | 20 | 0.400 | 0.750 | 0.750 | 0.575 | 0.621 |

short-copy subset (robustness view): the longest copied run is under 5 tokens; judge leakage labels are ignored

| config | n | recall@1 | recall@5 | recall@10 | mrr | ndcg@10 |
|---|---|---|---|---|---|---|
| production | 49 | 0.388 | 0.837 | 0.898 | 0.600 | 0.675 |

recall@10 by category

| config | conceito | fato_pontual | procedimento |
|---|---|---|---|
| production | 0.909 (n=11) | 0.944 (n=18) | 0.900 (n=30) |

queries with recall@10 = 0 under best config (production): 5

- r1-clt-041 [procedimento] Como é calculado o pagamento mensal dos professores com base nas aulas semanais e nas faltas?
- r1-clt-044 [procedimento] Os municípios podem criar regras que contrariem as normas e instruções federais sobre o funcionamento dessas atividades?
- r1-cpc-000 [procedimento] Quais são os requisitos para que a eleição de foro tenha validade em um contrato?
- r1-cpc-004 [fato_pontual] Quando a desistência da ação passa a ter efeito legal?
- r1-cpc-016 [conceito] Quais são as defesas que podem ser apresentadas nesse tipo de processo?
