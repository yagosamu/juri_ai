# PRD — Juri AI

## Produto

**Nome:** Juri AI
**Tipo:** SaaS multi-tenant para escritórios de advocacia
**Descrição:** Plataforma de inteligência artificial jurídica que automatiza análise de documentos processuais, atendimento ao cliente e agendamento, integrando-se aos sistemas e canais já usados por advogados (WhatsApp, Google Calendar, tribunais federais via DataJud/CNJ).

---

## Público-alvo

**Primário:** Advogados autônomos e pequenos escritórios de advocacia que precisam escalar atendimento e análise processual sem aumentar equipe.

**Secundário:** Escritórios médios que querem automatizar triagem de documentos e atendimento inicial de clientes.

**Dores que resolve:**
- Tempo excessivo gasto em análise manual de petições e contratos
- Dificuldade de acompanhar prazos e processos em múltiplos tribunais
- Atendimento ao cliente limitado ao horário comercial e à disponibilidade humana
- Retrabalho por erros de formatação e coerência em peças processuais

---

## Agentes de IA

### 1. JuriAI — Assistente Jurídico
Assistente de Q&A jurídico com acesso à base de conhecimento do escritório (documentos do cliente indexados via RAG) e consulta em tempo real a processos judiciais.

**Capacidades:**
- Responde perguntas sobre documentos do cliente usando RAG (LanceDB, isolado por `cliente_id`)
- Busca processos judiciais na API pública do DataJud/CNJ em 50+ tribunais brasileiros (STJ, TST, TRFs, TJs, TRTs, TREs, STM)
- Memória persistente de conversas por sessão
- Respostas em streaming com log das referências consultadas

### 2. SecretariaAI — Secretária Virtual
Agente de atendimento automático via WhatsApp que representa o escritório, responde dúvidas sobre serviços e agenda reuniões.

**Capacidades:**
- Atendimento 24/7 via WhatsApp (Evolution API)
- Responde sobre produtos, serviços e preços do escritório (base de conhecimento `empresa`)
- Verifica disponibilidade e agenda reuniões no Google Calendar (restrito a 13h–18h)
- Memória de conversa por número de telefone (`session_id=phone`)
- Tom de vendedor: direciona o cliente para produtos e para agendamento com o advogado

### 3. JurisprudenciaAI — Analisador de Risco Documental
Especialista em análise estruturada de peças jurídicas: contratos, petições, contestações e recursos.

**Capacidades:**
- Índice de risco geral (0–100) com classificação: Baixo / Médio / Alto / Crítico
- Identificação de erros de coerência entre fatos e pedidos
- Levantamento de riscos jurídicos (fundamentos, legitimidade, competência)
- Verificação de problemas de formatação por padrões dos tribunais
- Red flags críticas que podem gerar indeferimento ou nulidade imediata
- Sugestões práticas e acionáveis para cada problema encontrado

---

## Integrações Ativas

| Integração | Finalidade | Status |
|---|---|---|
| OpenAI (GPT-4.1-mini / GPT-4o-mini) | LLM para todos os agentes | Ativo |
| LanceDB | Vector store para RAG (documentos e empresa) | Ativo |
| Docling | OCR e conversão de PDF/imagem para markdown | Ativo |
| CNJ DataJud API | Consulta de processos judiciais públicos | Ativo |
| Google Calendar API | Agendamento de reuniões via SecretariaAI | Ativo |
| Evolution API (WhatsApp) | Recebimento de mensagens e envio de respostas | Parcial — webhook ativo, envio comentado |

---

## Funcionalidades Planejadas

### Alta Prioridade
- [ ] Autenticação em todos os views e endpoints (vários views sem `@login_required`)
- [ ] BASE_URL e API KEY da Evolution API dinâmicos por cliente (hoje hardcoded em `wrapper_evolution_api.py`)

### Média Prioridade
- [ ] Dashboard de visão geral: documentos, processos, agenda, WhatsApp, riscos por cliente
- [ ] Home/landing page pública do SaaS
- [ ] Dados dinâmicos na view `/clientes` (hoje parcialmente estáticos)

### Visual / UX
- [ ] Modernização do design: sidebar, tipografia, paleta jurídica, responsividade mobile

### Futuro (backlog)
- [ ] Migração do banco de SQLite para PostgreSQL para produção
- [ ] Gestão de credenciais via variáveis de ambiente (Google OAuth hoje na raiz do projeto)
- [ ] Logs e observabilidade dos agentes
- [ ] Múltiplos usuários por escritório (hoje 1 `User` Django = 1 advogado)
- [ ] Envio ativo de mensagens WhatsApp (hoje só recebe)
- [ ] Notificações de prazos processuais

---

## Decisões Técnicas

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Framework web | Django 6.0.1 | Produtividade, ORM maduro, admin embutido |
| Agent framework | Agno 2.4.7 | Suporte nativo a RAG, memória, streaming e tools |
| LLM orchestration | Langchain (JurisprudenciaAI) | Structured output via Pydantic mais simples para análise determinística |
| Vector DB | LanceDB 0.27.1 | Embutido, sem servidor externo necessário em dev |
| OCR / Parsing | Docling 2.71.0 | Suporte a PDF, imagem, Word com saída markdown |
| Task queue | django-q2 | Integração nativa com Django ORM, sem Redis necessário |
| DB (dev) | SQLite | Zero configuração; memória dos agentes Agno também usa SQLite |
| WhatsApp | Evolution API | API não-oficial estável para WhatsApp Business |

**Multi-tenancy:** Isolamento de dados por `cliente_id` na camada de RAG (LanceDB metadata + `knowledge_filters`). Não há row-level security no banco relacional.

**Streaming:** Chat usa `StreamingHttpResponse` do Django com iteração de `RunOutputEvent` do Agno. Tool calls são persistidos como `ContextRag` para auditoria.
