# TASKS — JuriAI
> Controle de tarefas por fase e sprint | Atualizado: Abril 2026

---

## ✅ Concluído

### Segurança e Autenticação
- [x] Adicionar `@login_required` em todos os views desprotegidos
- [x] Adicionar verificação de ownership IDOR em `cliente()` e `analise_jurisprudencia()`
- [x] Configurar `LOGIN_URL = '/usuarios/login/'` no settings.py
- [x] Adicionar `X-CSRFToken` no fetch do chat

### Evolution API Dinâmica
- [x] Criar model `ConfiguracaoWhatsApp` com `EncryptedCharField` para api_key
- [x] Criar view e template `configuracao_whatsapp.html` com `@login_required`
- [x] Refatorar `wrapper_evolution_api.py` para receber credenciais do banco
- [x] Configurar `FIELD_ENCRYPTION_KEY` via `.env`

### Produto
- [x] Criar dashboard com dados reais (clientes, docs, alertas, Calendar)
- [x] Criar landing page pública (`home.html`)
- [x] Criar páginas de lista para Análise Jurídica e Jurisprudência
- [x] Redesign visual completo (sidebar, cards, tipografia, paleta)
- [x] Aplicar versão light na landing page

### Infraestrutura
- [x] Criar `.gitignore` (cobre `.env`, `db.sqlite3`, `lancedb/`, `token.json`, `venv/`)
- [x] Mover `SECRET_KEY` para `.env`
- [x] Configurar `ALLOWED_HOSTS` para desenvolvimento
- [x] Implementar view de logout
- [x] Corrigir bug CSRF no fetch do chat

---

## 🔴 FASE 0 — Segurança e LGPD
> Prioridade máxima — executar antes de qualquer nova feature

### Sprint 0.1 — Infraestrutura Crítica

- [x] **Migrar SQLite → PostgreSQL**
  - Instalar `psycopg2-binary`
  - Criar banco PostgreSQL local e em produção
  - Atualizar `DATABASES` no `settings.py`
  - Rodar `python manage.py migrate` no novo banco
  - Validar que todos os dados foram migrados corretamente

- [x] **Configurar settings de segurança HTTPS**
  - `SECURE_SSL_REDIRECT = True` (produção)
  - `SECURE_HSTS_SECONDS = 31536000`
  - `SESSION_COOKIE_SECURE = True`
  - `CSRF_COOKIE_SECURE = True`
  - `X_FRAME_OPTIONS = 'DENY'`

- [x] **Instalar e configurar django-axes (rate limiting)**
  - `pip install django-axes`
  - Adicionar em `INSTALLED_APPS` e `MIDDLEWARE`
  - Configurar: bloqueio após 5 tentativas, cooldown de 30 min
  - Testar que IPs são bloqueados após tentativas falhas

- [x] **Instalar django-auditlog nos models sensíveis**
  - `pip install django-auditlog`
  - Registrar: `Cliente`, `Documentos`, `User`, `ConfiguracaoWhatsApp`
  - Criar view de auditoria no admin

- [x] **Configurar AUTH_PASSWORD_VALIDATORS**
  - Mínimo 8 caracteres
  - Não pode ser apenas numérico
  - Não pode ser similar ao username
  - Não pode ser senha comum (lista de senhas fracas)

### Sprint 0.2 — Conformidade LGPD

- [ ] **Criar página /privacidade/**
  - Template standalone (sem sidebar)
  - Conteúdo: quais dados são coletados, finalidade, prazo de retenção, direitos do titular
  - Link no footer de todas as páginas

- [ ] **Criar página /termos/**
  - Template standalone
  - Conteúdo: termos de uso do serviço, limitações de responsabilidade
  - Link no footer de todas as páginas

- [ ] **Adicionar consentimento no cadastro**
  - Checkbox obrigatório: "Li e aceito os Termos de Uso e a Política de Privacidade"
  - Salvar data e versão do consentimento no model `User` ou tabela separada
  - Bloquear cadastro se checkbox não marcado

- [ ] **Implementar exclusão de conta**
  - View `/usuarios/excluir-conta/` com `@login_required`
  - Confirmação por senha antes de excluir
  - Deletar todos os dados do usuário: clientes, documentos, análises, configurações
  - Redirecionar para landing page após exclusão

- [ ] **Adicionar links LGPD no rodapé da landing page**
  - Link para /privacidade/
  - Link para /termos/
  - Texto: "© 2026 JuriAI · Privacidade · Termos"

---

## 🟠 FASE 1 — MVP Comercializável
> O advogado não assina sem essas funcionalidades

### Sprint 1.1 — Model de Processos

- [ ] **Criar model `Processo`**
  - Campos: `numero_cnj`, `vara`, `comarca`, `tribunal`, `tipo_acao`, `polo_ativo`, `polo_passivo`, `status` (ativo/arquivado/suspenso), `data_distribuicao`, `valor_causa`, `cliente` (FK), `user` (FK)
  - Migration gerada e aplicada
  - `__str__` retorna número CNJ formatado

- [ ] **CRUD completo de processos**
  - `listar_processos()` — lista todos os processos do usuário com filtro por status
  - `criar_processo()` — form com validação do número CNJ (formato TJ)
  - `editar_processo()` — edição inline
  - `arquivar_processo()` — soft delete (status = arquivado)
  - Todas as views com `@login_required` e verificação de ownership

- [ ] **Templates de processos**
  - `processos.html` — lista com filtros por status, tribunal, cliente
  - `processo.html` — detalhe com tabs: Andamentos | Documentos | Prazos | Honorários
  - Empty state quando não há processos

- [ ] **Adicionar Processos na sidebar**
  - Ícone de balança SVG inline
  - Active state: `url_name == 'lista_processos' or url_name == 'processo'`
  - Rota `/processos/` e `/processos/<id>/`

- [ ] **Vincular documentos e análises ao processo**
  - Adicionar campo `processo` (FK nullable) em `Documentos`
  - Migration e atualização do form de upload
  - Exibir documentos vinculados na aba "Documentos" do processo

### Sprint 1.2 — Controle de Prazos

- [ ] **Criar model `Prazo`**
  - Campos: `descricao`, `data_prazo`, `tipo` (audiência/protocolo/recurso/diligência/outro), `processo` (FK), `alerta_dias_antes` (default: 3), `status` (pendente/concluído/cancelado), `user` (FK)
  - Índice em `data_prazo` para queries de calendário

- [ ] **CRUD de prazos**
  - Criar/editar/concluir prazo dentro da página do processo
  - Listar prazos da semana no dashboard (substituir card "Em breve")
  - Filtro por status e tipo

- [ ] **View de agenda `/prazos/`**
  - Calendário mensal com prazos destacados por tipo (cor por tipo)
  - Lista de prazos dos próximos 30 dias
  - Adicionar "Agenda" na sidebar

- [ ] **Integração com Google Calendar**
  - Ao criar prazo, criar evento correspondente no Google Calendar automaticamente
  - Ao concluir/cancelar prazo, atualizar evento no Calendar
  - Tratar silenciosamente se Calendar não configurado

- [ ] **Alertas por e-mail**
  - Task `django-q` rodando diariamente às 8h
  - Envia e-mail para o advogado com prazos dos próximos `alerta_dias_antes` dias
  - Configurar SMTP no `.env`

### Sprint 1.3 — Andamentos DataJud

- [ ] **Criar model `AndamentoProcesso`**
  - Campos: `processo` (FK), `data`, `descricao`, `tipo`, `fonte` (DataJud/Manual)
  - Ordenado por data decrescente

- [ ] **Task assíncrona de consulta DataJud**
  - Task `django-q` que recebe `processo_id`
  - Busca andamentos pelo `numero_cnj` na API DataJud
  - Salva novos andamentos (evita duplicatas por data+descrição)
  - Atualiza `processo.ultima_atualizacao`

- [ ] **Atualização automática diária**
  - Schedule no `django-q` para consultar todos os processos ativos do usuário
  - Log de última consulta por processo

- [ ] **Timeline de andamentos na página do processo**
  - Aba "Andamentos" com timeline vertical
  - Badge "DataJud" ou "Manual" por andamento
  - Botão "Atualizar agora" (dispara task manualmente)

---

## 🟡 FASE 2 — Gestão Financeira

### Sprint 2.1 — Honorários

- [ ] **Criar model `Honorario`**
  - Campos: `cliente` (FK), `processo` (FK nullable), `descricao`, `valor_total`, `tipo` (fixo/êxito/hora/mensalidade), `vencimento`, `status` (pendente/pago/atrasado/cancelado), `user` (FK)
  - Property `esta_atrasado`: `vencimento < today and status == pendente`

- [ ] **CRUD de honorários**
  - Criar/editar/marcar como pago dentro da página do cliente e do processo
  - Listar todos os honorários em `/financeiro/`

- [ ] **Dashboard financeiro**
  - Card: Receita do mês (honorários pagos no mês atual)
  - Card: A receber (honorários pendentes)
  - Card: Em atraso (honorários atrasados)
  - Lista de inadimplentes

### Sprint 2.2 — Recebimentos e Relatórios

- [ ] **Model `Pagamento`**
  - Campos: `honorario` (FK), `valor_pago`, `data_pagamento`, `observacao`
  - Suporte a pagamentos parciais

- [ ] **Marcar como pago**
  - Botão na lista de honorários
  - Modal com: valor pago, data, observação
  - Atualiza status automaticamente se valor_pago >= valor_total

- [ ] **Relatório de fluxo de caixa**
  - View `/financeiro/relatorio/` com filtro por período
  - Tabela: entradas x saídas x saldo
  - Exportar como PDF (`reportlab` ou `weasyprint`)

- [ ] **Alerta de honorários vencidos via WhatsApp**
  - Task diária que verifica honorários atrasados
  - SecretariaAI envia mensagem ao advogado no WhatsApp

---

## 🟢 FASE 3 — Geração de Documentos com IA

### Sprint 3.1 — Templates de Documentos

- [ ] **Criar model `TemplateDocumento`**
  - Campos: `nome`, `tipo` (contrato/petição/notificação/procuração/outro), `conteudo_markdown` (com variáveis `{{cliente.nome}}`, `{{processo.numero}}`), `user` (FK nullable para templates globais)
  - Pré-popular com 5 templates padrão: contrato de honorários, procuração, notificação extrajudicial, petição inicial genérica, acordo extrajudicial

- [ ] **CRUD de templates**
  - View `/templates/` com lista e editor markdown inline
  - Duplicar template padrão para personalizar
  - Preview renderizado em tempo real

### Sprint 3.2 — Geração com IA

- [ ] **Criar agente `RedacaoAI`**
  - Agno + GPT-4
  - System prompt: especialista em redação jurídica brasileira
  - Recebe: tipo do documento + dados do cliente + dados do processo + instruções do advogado
  - Retorna: documento em markdown pronto para revisão

- [ ] **View de geração**
  - Form: selecionar template + selecionar cliente + selecionar processo (opcional) + instrução adicional
  - Chamada ao `RedacaoAI` com streaming
  - Editor inline para revisão e ajustes

- [ ] **Exportação**
  - Exportar como `.docx` (`python-docx`)
  - Exportar como `.pdf` (`weasyprint`)
  - Salvar como Documento vinculado ao cliente/processo

---

## 🔵 FASE 4 — CRM e Captação

### Sprint 4.1 — Pipeline de Leads

- [ ] **Criar model `Lead`**
  - Campos: `nome`, `telefone`, `email`, `origem` (WhatsApp/indicação/site/outro), `status` (novo/qualificado/proposta/fechado/perdido), `observacoes`, `user` (FK)

- [ ] **View kanban `/crm/`**
  - Colunas por status com drag-and-drop (JS nativo)
  - Card por lead: nome, origem, data, telefone
  - Adicionar "CRM" na sidebar

- [ ] **Converter lead em cliente**
  - Botão "Converter em cliente" no card do lead (status = fechado)
  - Pré-preenche o form de criação de cliente com dados do lead

### Sprint 4.2 — Captação via WhatsApp

- [ ] **SecretariaAI cria Lead automaticamente**
  - Ao receber mensagem de número desconhecido, cria `Lead` com status "novo"
  - Notifica advogado no dashboard (badge no menu CRM)

- [ ] **Relatório de conversão**
  - View `/crm/relatorio/` com funil: leads → qualificados → propostas → fechados
  - Taxa de conversão por origem

---

## 🟣 FASE 5 — Portal do Cliente e Mobile

### Sprint 5.1 — Portal do Cliente

- [ ] **Model de acesso para clientes finais**
  - `PortalCliente`: email, senha, `cliente` (OneToOne FK)
  - Autenticação separada do advogado

- [ ] **Portal `/portal/`**
  - Login exclusivo para clientes
  - Ver processos vinculados: status, andamentos recentes
  - Ver documentos disponibilizados pelo advogado
  - Enviar mensagem para o advogado

### Sprint 5.2 — PWA

- [ ] **Converter em Progressive Web App**
  - `manifest.json` com nome, ícone, cores
  - `service-worker.js` para cache offline básico
  - Meta tags no `base.html`

- [ ] **Push notifications**
  - Notificação de prazo chegando (via service worker)
  - Notificação de novo lead no CRM

---

## ⚫ FASE 6 — Análise Preditiva

### Sprint 6.1 — Jurimetria

- [ ] **Expandir JurisprudenciaAI com probabilidade de êxito**
  - Consultar casos similares no DataJud por tipo de ação + comarca
  - Calcular taxa de êxito histórica
  - Exibir score de probabilidade na página do processo

- [ ] **Relatório comparativo**
  - Casos similares: número, desfecho, tempo médio de duração
  - Insights estratégicos: "Casos como este têm 67% de êxito no TJSP"

---

## 📦 Backlog (sem sprint definido)

- [ ] Testes automatizados (pytest-django) — cobertura mínima 60%
- [ ] Observabilidade — logging estruturado nos agentes (Sentry ou similar)
- [ ] Escalabilidade — múltiplos workers no django-q para Docling pesado
- [ ] Corrigir `datetime.now()` congelado no startup do SecretariaAI
- [ ] Migração do banco de memória do Agno (my_memory_table) para PostgreSQL
- [ ] App mobile nativo (React Native) — pós-PMF
- [ ] Integração com PJe para peticionamento eletrônico
- [ ] Multi-tenancy (escritórios com múltiplos advogados e permissões)
- [ ] Planos e cobrança (Stripe ou Pagar.me)
- [ ] Painel de administração SaaS (métricas de uso, churm, MRR)

---

## 📊 Status Geral

| Fase | Status | Progresso |
|---|---|---|
| Fase 0 — Segurança | 🔴 Em andamento | 70% (Sprint 0.1 concluída, Sprint 0.2 LGPD pendente) |
| Fase 1 — MVP | ⬜ Não iniciada | 0% |
| Fase 2 — Financeiro | ⬜ Não iniciada | 0% |
| Fase 3 — Geração Docs | ⬜ Não iniciada | 0% |
| Fase 4 — CRM | ⬜ Não iniciada | 0% |
| Fase 5 — Portal/Mobile | ⬜ Não iniciada | 0% |
| Fase 6 — Preditiva | ⬜ Não iniciada | 0% |

---

*Última atualização: Abril 2026*
