# Out-of-scope question check

A question counts as out of scope only when both judges agree that none of the checked articles, complete or partial, contains any part of the answer.

| id | question | articles checked | gpt-4.1 (complete / partial) | claude-haiku-4-5 (complete / partial) | status |
|---|---|---|---|---|---|
| oos-01 | Qual é a pena prevista para o crime de estelionato? | 8 | none / none | none / none | out_of_scope |
| oos-02 | Com quantos pontos na carteira de habilitação o motorista tem o direito de dirigir suspenso? | 10 | none / none | none / none | out_of_scope |
| oos-03 | Até quando a pessoa física precisa entregar a declaração anual do Imposto de Renda? | 10 | none / none | none / none | out_of_scope |
| oos-04 | Quem herda primeiro quando alguém morre sem deixar testamento? | 10 | none / none | none / none | out_of_scope |
| oos-05 | Qual é o prazo de validade do passaporte comum brasileiro? | 10 | none / none | none / none | out_of_scope |
| oos-06 | Qual é a idade mínima para se candidatar a presidente da República? | 10 | none / none | none / none | out_of_scope |
| oos-07 | Qual é o valor da multa para quem não vota nas eleições? | 10 | none / none | none / none | out_of_scope |
| oos-08 | Qual é a pena para quem desmata área de preservação permanente? | 10 | none / none | none / none | out_of_scope |
| oos-09 | O condomínio pode proibir que moradores tenham animais de estimação? | 10 | none / none | none / none | out_of_scope |
| oos-10 | Quais documentos são necessários para registrar uma marca no INPI? | 10 | none / none | none / none | out_of_scope |

## Status counts

- out_of_scope: 10
- answerable: 0
- unverified: 0

## Token totals

- gpt-4.1: input 18612, output 1016
- claude-haiku-4-5: input 26354, output 1651

## Limitations

Only the union of BM25 top 5 and text-embedding-3-large top 5 articles is checked, so a relevant article that neither method surfaces is never shown to the judges. Article text is capped at 8000 characters, so a very long article is truncated before it reaches the judges. The judges come from two vendors, gpt-4.1 and claude-haiku-4-5, and there is no human legal review of these verdicts.
