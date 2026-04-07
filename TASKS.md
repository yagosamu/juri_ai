# TASKS.md — Juri AI

Tarefas priorizadas do projeto. Mover para "Em andamento" ao iniciar e marcar com [x] ao concluir.

---

## ALTA PRIORIDADE

- [x] **Verificar autenticação em todos os views e endpoints**
  - `usuarios/views.py`: `cliente()` não tem `@login_required` — qualquer pessoa com o ID consegue ver documentos e fazer upload
  - `ia/views.py`: `stream_resposta()`, `ver_referencias()`, `analise_jurisprudencia()`, `processar_analise()` sem autenticação
  - Verificar se há risco de vazamento de dados entre usuários diferentes

- [x] **Tornar BASE_URL e API KEY do Evolution API dinâmicos por cliente**
  - Hoje em `ia/wrapper_evolution_api.py`: `_BASE_URL` hardcoded como `'http://exemplo.com.br'` e `_API_KEY` como dict literal
  - Criar modelo de configuração por usuário/escritório ou ler de variáveis de ambiente
  - Desbloqueia o envio real de mensagens WhatsApp (linha comentada em `ia/views.py:140`)

---

## MÉDIA PRIORIDADE

- [x] **Alterar dados fixos em `/clientes` para dados dinâmicos do banco**
  - Resolvido junto com o Dashboard — counts reais exibidos na tela principal pós-login

- [x] **Criar dashboard de visualização geral**
  - Visão consolidada por escritório: total de clientes, documentos por status, processos acompanhados, reuniões agendadas, últimas análises de risco
  - Deve ser a tela pós-login (hoje redireciona direto para `/clientes`)

- [x] **Criar home/landing page pública do SaaS**
  - Página em `/` apresentando o produto, funcionalidades e CTA para cadastro/login
  - Sem autenticação necessária

---

## VISUAL

- [ ] **Modernizar o design geral**
  - Sidebar com navegação clara (Clientes, Dashboard, Processos, Agenda, WhatsApp)
  - Tipografia profissional e paleta de cores jurídica (tons sóbrios: azul-marinho, cinza, branco)
  - Responsividade mobile
  - Consistência visual entre todas as telas existentes (login, cadastro, clientes, cliente, chat, análise)

---

## BACKLOG (sem prioridade definida)

- [ ] Migrar banco de dados de SQLite para PostgreSQL
- [ ] Mover credenciais Google OAuth da raiz do projeto para variáveis de ambiente
- [ ] Corrigir `datetime.now()` no prompt da `SecretariaAI` (avaliado no startup, não por requisição)
- [ ] Implementar envio ativo de mensagens WhatsApp (descomentar e configurar `SendMessage` em `webhook_whatsapp`)
- [ ] Adicionar logging estruturado nos agentes para observabilidade
- [ ] Suporte a múltiplos usuários por escritório
- [ ] Notificações automáticas de prazos processuais
