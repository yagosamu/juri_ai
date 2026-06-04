# PRD — JuriAI
> Documento de Produto | Versão 2.1 | Junho 2026

---

## 1. Visão do Produto

**JuriAI** é um SaaS jurídico com inteligência artificial para advogados autônomos e pequenos escritórios de advocacia. A plataforma automatiza tarefas operacionais repetitivas — atendimento, análise de documentos, agendamento — liberando o advogado para focar na estratégia e no crescimento do escritório.

**Tagline:** *Seu escritório trabalhando 24h — com ou sem você.*

---

## 2. Público-Alvo

| Perfil | Descrição | Dor principal |
|---|---|---|
| **Primário** | Advogado autônomo (solo) | Sobrecarregado com tarefas administrativas, sem equipe de suporte |
| **Secundário** | Pequenos escritórios (2–10 advogados) | Dificuldade de escalar sem contratar mais pessoas |
| **Futuro** | Escritórios médios (10–50 advogados) | Falta de visibilidade estratégica e analytics |

---

## 3. Problema que Resolve

1. **Horas perdidas revisando petições** — advogado gasta horas lendo documentos antes do protocolo
2. **Clientes sem resposta fora do horário** — WhatsApp silencioso à noite e nos fins de semana
3. **Agenda desorganizada** — conflitos de horário e reuniões perdidas
4. **Prazos esquecidos** — risco de perder prazo processual por falta de controle
5. **Gestão financeira manual** — honorários controlados em planilha ou caderno

---

## 4. Os 3 Agentes de IA

### JuriAI (Agno + RAG)
- Responde perguntas jurídicas com base nos documentos do cliente
- Memória de longo prazo por cliente (`update_memory_on_run=True`)
- Busca processos em 50+ tribunais via DataJud/CNJ
- Base vetorial isolada por cliente no LanceDB

### SecretariaAI (Agno + Evolution API)
- Atende clientes no WhatsApp 24h automaticamente
- Agenda reuniões e cria eventos no Google Calendar
- Histórico de conversa por número de telefone (`session_id=phone_number`)
- Cria leads automaticamente para novos contatos

### JurisprudenciaAI (LangChain + GPT-4 mini)
- Analisa petições e contratos
- Gera score de risco 0–100
- Identifica red flags, erros e inconsistências

### RedacaoAI (Agno + GPT-4)
- Gera minutas jurídicas a partir de templates e instruções do advogado
- Substitui variáveis de cliente, processo, honorários e data atual
- Exporta documentos revisados em PDF e DOCX

---

## 5. Integrações Ativas

| Integração | Status | Observação |
|---|---|---|
| OpenAI (GPT-4 / GPT-4 mini) | ✅ Ativo | Todos os agentes |
| Google Calendar | ✅ Ativo | OAuth — token.json gerado na 1ª execução |
| Evolution API (WhatsApp) | ✅ Ativo | Credenciais dinâmicas por usuário |
| CNJ DataJud | ✅ Ativo | Busca de processos por número CNJ |
| LanceDB | ✅ Ativo | RAG vetorial por cliente |
| PostgreSQL | ✅ Ativo | Banco de produção e suporte a `DATABASE_URL` |
| SMTP (e-mail) | ✅ Ativo | Alertas de prazo por e-mail |
| ReportLab / OpenPyXL / python-docx | ✅ Ativo | Exportação de relatórios e documentos |

---

## 6. Stack Técnica

| Camada | Tecnologia | Decisão |
|---|---|---|
| Backend | Django 6 + Python 3.13 | Framework maduro, admin gratuito |
| Agentes IA | Agno (JuriAI, SecretariaAI) + LangChain (Jurisprudência) | Agno para memória/RAG, LangChain para pipeline de análise |
| Vetorial | LanceDB | Leve, sem servidor, isolamento por cliente |
| Fila de tasks | django-q | OCR assíncrono, alertas, atualizações DataJud |
| OCR/Parsing | Docling | Conversão de PDF/DOCX para markdown |
| WhatsApp | Evolution API | Self-hosted, webhook via POST |
| Frontend | Django Templates + Tailwind CDN | Server-side rendering, sem SPA |
| Banco produção | PostgreSQL | Confiabilidade, concorrência e LGPD |
| Banco desenvolvimento | PostgreSQL local ou SQLite auxiliar | Configurável por ambiente |

---

## 7. Segurança e Conformidade LGPD

### Requisitos técnicos obrigatórios

| Prioridade | Item | Implementação |
|---|---|---|
| 🔴 Crítico | Rate limiting no login | `django-axes` |
| 🔴 Crítico | HTTPS obrigatório | `SECURE_SSL_REDIRECT = True` + SSL |
| 🔴 Crítico | Logs de auditoria | `django-auditlog` |
| 🔴 Crítico | Migração para PostgreSQL | Concluída |
| 🟡 Alto | 2FA (dois fatores) | `django-two-factor-auth` |
| 🟡 Alto | Headers de segurança HTTP | `SecurityMiddleware` ativo; CSP dedicado no backlog |
| 🟡 Alto | Política de senhas forte | `AUTH_PASSWORD_VALIDATORS` |
| 🟢 Médio | Termos de uso + Política de privacidade | Páginas estáticas — obrigatórias LGPD |
| 🟢 Médio | Consentimento no cadastro | Checkbox obrigatório |
| 🟢 Médio | Exclusão de conta e dados | Direito do titular — art. 18 LGPD |

### Contexto regulatório
- Dados de processos e clientes são **dados pessoais sensíveis** sob a LGPD
- A ANPD tem poder real de multa desde 2026 — custo médio de violação no Brasil: R$ 7,19 milhões
- Plataformas jurídicas são alvo prioritário de fiscalização por tratarem dados sigilosos
- Obrigações: política de privacidade publicada, consentimento explícito, direito de exclusão, notificação de incidentes

---

## 8. Roadmap por Fases

| Fase | Status | Entregas principais |
|---|---|---|
| Fase 0 — Segurança e LGPD | ✅ Concluída | PostgreSQL, HTTPS, django-axes, auditlog, consentimento, termos, privacidade e exclusão de conta |
| Fase 1 — MVP Comercializável | ✅ Concluída | Clientes, processos, prazos, agenda, DataJud e alertas |
| Fase 2 — Gestão Financeira | ✅ Concluída | Honorários, pagamentos, fluxo de caixa, PDF/Excel e alertas |
| Fase 3 — Geração de Documentos IA | ✅ Concluída | Templates, RedacaoAI, editor, salvamento, PDF e DOCX |
| Fase 4 — CRM e Captação | ✅ Concluída | Pipeline de leads, conversão, relatório e leads via WhatsApp |
| Fase 5 — Calculadora Judicial | ✅ Concluída | Índices econômicos, cálculo judicial, trabalhista, tabelas TJ, múltiplas parcelas e cenários |

### Backlog público

- Portal do Cliente
- PWA e notificações push
- Análise preditiva e jurimetria
- Observabilidade estruturada
- Multi-tenancy para escritórios com múltiplos advogados
- Planos e cobrança

---

## 9. Comparativo com Concorrentes

| Funcionalidade | JuriAI | EasyJur | Projuris | Astrea | ADVBOX |
|---|---|---|---|---|---|
| RAG por cliente | ✅ | ❌ | ❌ | ❌ | ❌ |
| Atendimento WhatsApp IA | ✅ | ❌ | ❌ | ❌ | ❌ |
| Análise de risco de petições | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gestão de processos | ✅ | ✅ | ✅ | ✅ | ✅ |
| Controle de prazos | ✅ | ✅ | ✅ | ✅ | ✅ |
| Gestão financeira | ✅ | ✅ | ✅ | ✅ | ✅ |
| Geração de documentos IA | ✅ | Parcial | ❌ | ❌ | Parcial |
| CRM jurídico | ✅ | ✅ | ✅ | ❌ | ✅ |
| Calculadora judicial | ✅ | Parcial | Parcial | Parcial | Parcial |
| Portal do cliente | Backlog | ✅ | ✅ | ❌ | ✅ |
| App mobile | Backlog | ✅ | ✅ | ✅ | ✅ |
| Análise preditiva | Backlog | ❌ | ❌ | ❌ | ❌ |

**Conclusão:** JuriAI já cobre a base operacional de um escritório pequeno e diferencia-se pela camada de IA aplicada a documentos, atendimento, RAG e cálculos judiciais.

---

## 10. Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| ORM | Django ORM | Padrão do framework, sem overhead |
| Autenticação | Django Auth nativo | Simples, maduro e integrado ao admin |
| Banco desenvolvimento | PostgreSQL local ou SQLite auxiliar | Configurável por ambiente |
| Banco produção | PostgreSQL | Confiabilidade, concorrência, LGPD |
| Fila assíncrona | django-q | Já integrado; Celery seria over-engineering para o estágio atual |
| RAG | LanceDB | Leve, sem servidor, isolamento por cliente |
| Frontend | Server-side (Django templates) | Sem SPA — menor complexidade para MVP |
| CSS | Tailwind CDN | Suficiente para MVP sem build step |

---

*Última atualização: Junho 2026*
