# PRD: JuriAI
> Documento de Produto | Versão 3.0 | Setembro 2026

---

## 1. Visão do Produto

**JuriAI** é um SaaS jurídico com inteligência artificial para advogados autônomos e pequenos escritórios de advocacia. A plataforma automatiza tarefas operacionais repetitivas, como atendimento, análise de documentos, agendamento, prazos e cálculos, e deixa o advogado livre para a estratégia e o crescimento do escritório.

**Tagline:** *Seu escritório trabalhando 24h, com ou sem você.*

**Princípio desde a versão 3.0:** a qualidade da IA é medida, não presumida. Toda mudança na busca do agente jurídico passa por um conjunto de avaliação versionado e por um gate de regressão no CI (seção 6).

---

## 2. Público-Alvo

| Perfil | Descrição | Dor principal |
|---|---|---|
| **Primário** | Advogado autônomo (solo) | Sobrecarregado com tarefas administrativas, sem equipe de suporte |
| **Secundário** | Pequenos escritórios (2 a 10 advogados) | Dificuldade de escalar sem contratar mais pessoas |
| **Futuro** | Escritórios médios (10 a 50 advogados) | Falta de visibilidade estratégica e analytics |

---

## 3. Problema que Resolve

1. **Horas perdidas revisando petições**: o advogado gasta horas lendo documentos antes do protocolo.
2. **Clientes sem resposta fora do horário**: WhatsApp silencioso à noite e nos fins de semana.
3. **Agenda desorganizada**: conflitos de horário e reuniões perdidas.
4. **Prazos esquecidos**: risco de perder prazo processual por falta de controle.
5. **Gestão financeira manual**: honorários controlados em planilha ou caderno.
6. **Cálculos judiciais demorados**: correção monetária, juros e cenários feitos à mão.

---

## 4. Funcionalidades

### 4.1 Gestão do escritório

| Módulo | O que faz | Modelos principais |
|---|---|---|
| Clientes e processos | Cadastro de clientes, processos, andamentos e links, com consulta ao DataJud/CNJ | `Cliente`, `Processo`, `AndamentoProcesso`, `LinkProcesso` |
| Documentos | Upload, OCR assíncrono e indexação para o RAG | `Documentos` |
| Prazos e agenda | Prazos processuais, eventos no Google Calendar e alertas por e-mail | `Prazo` |
| Financeiro | Honorários, pagamentos, inadimplência, fluxo de caixa, exportação PDF e Excel | `Honorario`, `Pagamento` |
| Geração de documentos | Templates, minutas por IA, editor e exportação PDF e DOCX | `TemplateDocumento`, `DocumentoGerado` |
| CRM | Pipeline de leads, conversão em cliente, relatório e leads vindos do WhatsApp | `Lead` |
| Calculadora judicial | Índices econômicos, correção, juros, tabelas de tribunal, cálculo trabalhista, múltiplas parcelas e comparação de cenários | `IndiceEconomico`, `CalculoJudicial` |
| LGPD | Consentimento registrado, termos, privacidade e exclusão de conta | `ConsentimentoLGPD` |

### 4.2 Os 4 agentes de IA

| Agente | Stack e modelo | O que faz |
|---|---|---|
| **JuriAI** | Agno 2.4.7, modelo padrão do Agno (gpt-4o), LanceDB | Responde perguntas jurídicas sobre os documentos do cliente (RAG com filtro `cliente_id`), consulta processos no DataJud/CNJ e mantém memória de longo prazo (`update_memory_on_run=True`) |
| **SecretariaAI** | Agno, gpt-4o-mini, Evolution API, Google Calendar | Atende no WhatsApp, agenda reuniões entre 13h e 18h e cria leads para contatos novos; histórico por telefone (`session_id=phone_number`) |
| **JurisprudenciaAI** | LangChain, gpt-4.1-mini, saída estruturada Pydantic | Analisa petições e contratos: `indice_risco` de 0 a 100, erros de coerência, riscos jurídicos, problemas de formatação e red flags |
| **RedacaoAI** | Agno, gpt-4o | Gera minutas a partir de templates, dados do cliente, do processo e instruções do advogado |

### 4.3 Pipeline de documentos

Upload, então signal do Django, então `Chain` do django-q com duas tarefas em sequência (`ia/tasks.py`):
1. `ocr_and_markdown_file`: o Docling converte PDF ou imagem em markdown, salvo em `Documentos.content`.
2. `rag_documentos`: o markdown entra no LanceDB (tabela `documentos`) com o metadado `cliente_id`.

A configuração da busca (embedder, chunking, tipo de busca, distância, número de resultados, reranker) é explícita em `ia/retrieval_config.py`, para que a avaliação meça exatamente o que a produção roda.

---

## 5. Integrações Ativas

| Integração | Status | Observação |
|---|---|---|
| OpenAI | Ativo | Agentes (gpt-4o, gpt-4o-mini, gpt-4.1-mini) e embeddings (`text-embedding-3-small`, 1536 dimensões) |
| LanceDB | Ativo | RAG vetorial com filtro por cliente (ver limitações, seção 9) |
| Evolution API (WhatsApp) | Ativo | Credenciais por usuário, criptografadas no banco |
| Google Calendar | Ativo | OAuth |
| CNJ DataJud | Ativo | Consulta de metadados públicos de processos; chave pública centralizada em settings |
| PostgreSQL | Ativo | Banco de produção via `DATABASE_URL` |
| Langfuse | Opcional, desligado por padrão | Observabilidade de LLM com mascaramento de dados pessoais (seção 7) |
| SMTP | Ativo | Alertas de prazo e financeiros |
| ReportLab, OpenPyXL, python-docx | Ativo | Exportação de relatórios e documentos |

---

## 6. Qualidade da IA: Groundtruth

Groundtruth (`evals/groundtruth/`) é o harness de avaliação do RAG do JuriAI. Foi construído em setembro de 2026 e roda offline, sem chamada de API, a partir de caches versionados.

### 6.1 Como funciona

- **Corpus:** 4 leis públicas (CPC, CDC, CLT, LGPD), normalizadas e com manifesto.
- **Golden set:** 59 perguntas, cada uma ligada a um trecho exato do texto (spans de caracteres). As perguntas foram selecionadas por consenso de dois juízes (gpt-4.1 e claude-haiku-4-5, rubrica v2), com calibração cega. Há também perguntas fora de escopo verificadas contra o corpus.
- **Métricas:** recall@1, @5 e @10, MRR e nDCG@10, com regra de acerto bidirecional sobre spans.
- **Configurações comparadas:** production (5000/0, vetorial), chunk1500, chunk800, hybrid e rerank (bge-reranker-v2-m3).
- **Significância:** intervalos de bootstrap e testes pareados pré-registrados (McNemar exato, bootstrap e sign-flip para MRR), com correção de Holm.
- **Geração:** faithfulness e answer relevancy do agente JuriAI real, pontuadas pelo DeepEval, separadas da avaliação de retrieval.

### 6.2 Resultados medidos

Fonte: `evals/groundtruth/results/`.

| Configuração | recall@1 | recall@10 | MRR |
|---|---|---|---|
| production (atual) | 0.373 | 0.915 | 0.594 |
| chunk1500 | 0.712 | 0.932 | 0.811 |
| hybrid | 0.695 | 0.966 | 0.806 |
| rerank | 0.881 | 0.966 | 0.921 |

- **Recomendação medida:** chunk1500 como padrão. Os ganhos de recall@1 e MRR sobre production são significativos após Holm (p=0.0004 e 0.0010); o de recall@10 não é. Ainda não foi implantado.
- **Rerank** tem os melhores números de ranking, mas a busca leva 45356 ms no p50, porque o agno 2.4.7 recarrega o modelo a cada chamada.
- **Geração:** faithfulness média de 0.952 (n=29) e relevancy de 0.983 (n=30).
- **Abstenção:** o agente não se absteve em nenhuma das 7 perguntas fora de escopo concluídas (0 de 7); 3 das 10 falharam por limite de tokens por minuto.

### 6.3 Gate de regressão no CI

- **`groundtruth.yml`:** roda os testes a cada pull request, a cada push na main e por disparo manual. Reprova se o recall@10 de produção cair mais de 0.01 ou o MRR mais de 0.02 abaixo de `baseline.json`. Demonstrado no PR #12, em que `MAX_RESULTS=3` derrubou o recall@10 de 0.915 para 0.780 e o check reprovou.
- **`groundtruth-baseline-label.yml`:** reprova quando um PR altera o baseline, o golden set, o índice ou o cache de consultas sem o rótulo `baseline-change`. Num repositório com um único mantenedor, isso é uma trava de atenção, não um controle de autorização.

### 6.4 Revisão humana

- 20 itens do golden set, numa planilha cega entregue a um advogado com registro ativo na OAB. A revisão está em andamento.
- Quando as respostas voltarem, a concordância entre o advogado e os juízes automáticos será publicada no README do Groundtruth.

---

## 7. Observabilidade

- Camada opcional com Langfuse, ligada pela variável `LANGFUSE_ENABLED` e desligada por padrão.
- Cobre os dois motores: LangChain via callback e Agno via OpenInference e OpenTelemetry.
- Cada chamada de agente gera um trace com tokens, custo, latência e modelo.
- **Privacidade:** um mascaramento por allowlist fechada roda no momento da exportação e remove todo o conteúdo do cliente (texto de documentos, nomes, CPFs, mensagens). Prompt e resposta nunca saem da aplicação.

---

## 8. Segurança e Conformidade LGPD

### Situação dos requisitos

| Prioridade | Item | Situação |
|---|---|---|
| Crítico | Rate limiting no login | Implementado: `django-axes`, 5 tentativas, bloqueio de 30 minutos |
| Crítico | HTTPS obrigatório | Implementado em produção: `SECURE_SSL_REDIRECT` e HSTS de 1 ano |
| Crítico | Logs de auditoria | Implementado: `django-auditlog` |
| Crítico | PostgreSQL em produção | Implementado |
| Crítico | Credenciais de terceiros criptografadas | Implementado: campo criptografado com `FIELD_ENCRYPTION_KEY` |
| Alto | Política de senhas forte | Implementado: `AUTH_PASSWORD_VALIDATORS` |
| Alto | Headers de segurança HTTP | Parcial: `SecurityMiddleware` e nosniff ativos; CSP dedicado no backlog |
| Alto | 2FA | Não implementado; backlog |
| Médio | Termos de uso e política de privacidade | Implementado: `/termos/` e `/privacidade/` |
| Médio | Consentimento no cadastro | Implementado: `ConsentimentoLGPD` |
| Médio | Exclusão de conta e dados (art. 18 da LGPD) | Implementado: `/excluir-conta/` |
| Médio | Dados de clientes fora dos traces de IA | Implementado: mascaramento na exportação (seção 7) |

### Contexto regulatório
- Dados de processos e de clientes incluem dados pessoais, muitas vezes sensíveis, sob a LGPD.
- Plataformas jurídicas tratam dados sigilosos e são alvo natural de fiscalização.
- Obrigações: política de privacidade publicada, consentimento explícito, direito de exclusão e notificação de incidentes.

---

## 9. Limitações Conhecidas

| Limitação | Detalhe | Direção |
|---|---|---|
| Filtro `cliente_id` depois do top-k | O agno 2.4.7 busca as 10 linhas mais próximas e só depois filtra por cliente. Medido com 2 clientes: 26 de 59 perguntas receberam menos de 10 trechos; buscando pelo cliente que não é dono do documento, 33 de 59 receberam 0. Nenhum vazamento entre clientes em 236 buscas | Over-fetch ×10 já mitiga no harness de avaliação; no app, exige `cliente_id` como coluna (mudança no agno ou banco vetorial próprio) |
| Isolamento só na camada de RAG | Não há row-level security no banco | Avaliar junto com multi-tenancy de escritórios |
| Índice vetorial efêmero no Render | `render.yaml` define `DATA_DIR=/tmp/juri-ai` | Armazenamento persistente antes de escalar |
| Chunking de produção | 5000 caracteres sem overlap; recall@1 de 0.373 | Adotar chunk1500 (medido, ainda não implantado) |
| Abstenção | 0 de 7 perguntas fora de escopo concluídas terminaram em abstenção | Instrução e limiar de abstenção, medidos pelo Groundtruth |
| Tokens por turno | 3 de 10 execuções fora de escopo passaram de 30000 tokens por minuto | Limitar o contexto por turno |
| Data fixa na SecretariaAI | A data e hora nas instruções são calculadas quando o servidor sobe | Montar as instruções por requisição |
| Plano gratuito do Render | Web e banco no plano free | Plano pago antes de clientes reais |

---

## 10. Roadmap

| Fase | Status | Entregas principais |
|---|---|---|
| Fase 0: Segurança e LGPD | Concluída | PostgreSQL, HTTPS, django-axes, auditlog, consentimento, termos, privacidade e exclusão de conta |
| Fase 1: MVP comercializável | Concluída | Clientes, processos, prazos, agenda, DataJud e alertas |
| Fase 2: Gestão financeira | Concluída | Honorários, pagamentos, fluxo de caixa, PDF e Excel, alertas |
| Fase 3: Geração de documentos por IA | Concluída | Templates, RedacaoAI, editor, PDF e DOCX |
| Fase 4: CRM e captação | Concluída | Pipeline de leads, conversão, relatório e leads via WhatsApp |
| Fase 5: Calculadora judicial | Concluída | Índices, cálculo judicial e trabalhista, tabelas de tribunal, parcelas e cenários |
| Fase 6: Observabilidade de IA | Concluída (julho 2026) | Langfuse opcional, OpenTelemetry e OpenInference, mascaramento de dados pessoais |
| Fase 7: Avaliação e qualidade do RAG | Concluída (setembro 2026) | Groundtruth: golden set, 5 configurações, significância, avaliação de geração, gate de CI, medição multi-cliente |
| Fase 8: Aplicar o que foi medido | Próxima | chunk1500 em produção, controle de tokens por turno, abstenção |

### Backlog

- **Avaliação:** golden set de 59 para 100 perguntas; cache do reranker; concordância com a revisão do advogado.
- **Infraestrutura:** índice vetorial persistente; avaliar a migração para Azure AI Search, com antes e depois medidos pelo Groundtruth; pré-filtro real por `cliente_id`.
- **Segurança:** 2FA e CSP dedicado.
- **Produto:** portal do cliente, PWA e notificações push, análise preditiva e jurimetria, multi-tenancy para escritórios com vários advogados, planos e cobrança.

---

## 11. Comparativo com Concorrentes

Levantamento de junho de 2026, não reverificado desde então.

| Funcionalidade | JuriAI | EasyJur | Projuris | Astrea | ADVBOX |
|---|---|---|---|---|---|
| RAG sobre documentos do cliente | Sim | Não | Não | Não | Não |
| Atendimento por IA no WhatsApp | Sim | Não | Não | Não | Não |
| Análise de risco de petições | Sim | Não | Não | Não | Não |
| Gestão de processos | Sim | Sim | Sim | Sim | Sim |
| Controle de prazos | Sim | Sim | Sim | Sim | Sim |
| Gestão financeira | Sim | Sim | Sim | Sim | Sim |
| Geração de documentos por IA | Sim | Parcial | Não | Não | Parcial |
| CRM jurídico | Sim | Sim | Sim | Não | Sim |
| Calculadora judicial | Sim | Parcial | Parcial | Parcial | Parcial |
| Portal do cliente | Backlog | Sim | Sim | Não | Sim |
| App mobile | Backlog | Sim | Sim | Sim | Sim |
| Análise preditiva | Backlog | Não | Não | Não | Não |

**Conclusão:** o JuriAI cobre a base operacional de um escritório pequeno e se diferencia pela camada de IA aplicada a documentos, atendimento e cálculos. Além disso, a qualidade do RAG é medida de forma reproduzível e protegida por um gate de CI.

---

## 12. Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| Backend | Django 6; Python 3.12 no CI, 3.13 no Render | Framework maduro, admin pronto |
| ORM e autenticação | Django ORM e Django Auth | Padrão do framework, integrado ao admin |
| Banco | PostgreSQL em produção; configurável no desenvolvimento | Confiabilidade, concorrência e LGPD |
| Fila assíncrona | django-q2 | Já integrado; Celery seria excesso para o estágio atual |
| Agentes | Agno para memória e RAG; LangChain para a análise estruturada | Cada motor onde é mais simples |
| Banco vetorial | LanceDB | Leve e sem servidor; a limitação do filtro está medida (seção 9) |
| Configuração de retrieval | Explícita em `ia/retrieval_config.py` | Permite medir exatamente o que roda em produção |
| Avaliação | Harness próprio, offline, com caches versionados | Reproduzível a partir de um clone, sem custo de API no CI |
| Observabilidade | Langfuse opcional, com mascaramento na exportação | Métricas operacionais sem expor dado sigiloso |
| Frontend | Django templates e Tailwind CDN | Sem SPA e sem build step no estágio de MVP |
| Deploy | Render (`render.yaml`, `build.sh`, `start.sh`) | Deploy simples a partir do repositório |

---

*Última atualização: setembro de 2026*
