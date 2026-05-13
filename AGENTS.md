# AGENTS.md — Instruções para o Codex (Claude Code)
> Este arquivo define como o Codex deve executar cada task do projeto JuriAI.

---

## 🏗️ Projeto

**JuriAI** — SaaS jurídico para advogados brasileiros com 3 agentes IA.

- **Stack:** Django 6, Python 3.13, PostgreSQL 17.5, Agno 2.5.5, Tailwind CDN
- **Localização do projeto:** `C:\Users\Yago\desktop\asimov\projetos_ia\juri_ai`
- **Venv:** `venv\` na raiz do projeto (sempre ativar antes de rodar comandos)
- **Usuário de teste:** `teste2 / abc123`

---

## 📋 Referências obrigatórias

Antes de iniciar qualquer task, leia:
- **CLAUDE.md** — convenções do projeto, estrutura de pastas, padrões de código
- **TASKS.md** — roadmap completo, status de cada fase e sprint
- **PRD.md** — visão do produto, requisitos e decisões de arquitetura

---

## ⚙️ Workflow por task

Cada task segue este fluxo obrigatório:

### 1. Diagnóstico (antes de alterar qualquer arquivo)
- Verificar quais arquivos serão impactados
- Verificar se existem models/views/templates relacionados
- Verificar dependências (pip list | grep <pacote>)
- Mostrar o plano de implementação

### 2. Implementação
- Aplicar as alterações conforme o plano
- Seguir as convenções do projeto (ver CLAUDE.md):
  - Todas as views com `@login_required`
  - Ownership check via `get_object_or_404(Model, id=id, user=request.user)`
  - Templates estendem `base.html` com `{% block 'content' %}`
  - Inputs de data: `type="text"` com `data-mask="date"` e `placeholder="dd/mm/yyyy"`
  - Inputs de moeda: `type="text"` com `data-mask="currency"` e `placeholder="0,00"`
  - Datas no backend: usar helper `_parse_date_br()` de `usuarios/views.py`
  - Decimais no backend: usar helper `_parse_decimal_br()` de `usuarios/views.py`
  - Exibição de valores: `{{ valor|floatformat:"2g" }}` com prefixo `R$`

### 3. Verificação
- Rodar `python manage.py makemigrations` (se models alterados)
- Rodar `python manage.py migrate`
- Rodar `python manage.py check` — deve retornar 0 issues
- Testar no shell se necessário (ex: verificar dados populados)
- Confirmar que URLs resolvem corretamente

### 4. Entrega
- Mostrar resumo do que foi alterado/criado
- Listar arquivos modificados com descrição do que mudou
- Confirmar que `manage.py check` está limpo
- **NÃO fazer commit** — o commit é feito manualmente após revisão

---

## 🗂️ Estrutura do projeto

```
juri_ai/
├── core/                    # settings.py, urls.py, wsgi.py
├── ia/                      # Agentes IA, views IA, tasks assíncronas
│   ├── agents.py            # JuriAI, SecretariaAI, JurisprudenciaAI, RedacaoAI
│   ├── views.py             # Chat, streaming, análise, geração docs, webhook
│   ├── tasks.py             # Tasks django-q (DataJud, alertas)
│   ├── exportacao.py        # gerar_docx(), gerar_pdf()
│   ├── urls.py
│   └── templates/           # Templates do app ia
├── usuarios/                # App principal: clientes, processos, financeiro, CRM
│   ├── models.py            # Cliente, Processo, Honorario, Lead, TemplateDocumento, etc.
│   ├── views.py             # CRUD completo de todos os models
│   ├── urls.py
│   ├── templatetags/
│   │   └── crm_tags.py      # Template tag leads_novos
│   └── templates/           # Templates do app usuarios
├── templates/               # Templates globais (base.html, home.html, etc.)
├── CLAUDE.md                # Convenções e decisões do projeto
├── PRD.md                   # Product Requirements Document
├── TASKS.md                 # Roadmap e controle de sprints
└── AGENTS.md                # Este arquivo
```

---

## 🎨 Padrões visuais

- **Paleta:** blue-800 (azul royal) como cor primária, slate para neutros
- **Sidebar:** slate-950, itens com active state em indigo-600
- **Cards:** bg-white, border-slate-100/200, rounded-2xl, shadow-sm
- **Badges:** verde=sucesso, vermelho=erro/crítico, amber=alerta, azul=info
- **Botões primários:** bg-indigo-600 hover:bg-indigo-500
- **Botões secundários:** border border-slate-200 hover:bg-slate-50
- **Tipografia:** text-sm para corpo, text-xs para labels, font-semibold para headings
- **Framework CSS:** Tailwind CDN (não instalar via npm)

---

## 🔧 Convenções de código

### Models (usuarios/models.py)
```python
class MeuModel(models.Model):
    TIPO_CHOICES = [('chave', 'Label'), ...]
    campo = models.CharField(max_length=200, verbose_name='Label')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meus_models')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Meu Model'

    def __str__(self):
        return self.campo

# Sempre registrar no auditlog:
auditlog.register(MeuModel)
```

### Views (usuarios/views.py)
```python
@login_required
def minha_view(request, id):
    obj = get_object_or_404(MeuModel, id=id, user=request.user)  # ownership!
    if request.method == 'POST':
        # processar...
        messages.success(request, 'Sucesso!')
        return redirect('nome_da_url')
    return render(request, 'meu_template.html', {'obj': obj})
```

### URLs (usuarios/urls.py)
```python
# Agrupar por feature com comentário
# ── Minha Feature ──────────────────────────────────────────
path('feature/', views.lista_feature, name='lista_feature'),
path('feature/novo/', views.criar_feature, name='criar_feature'),
path('feature/<int:id>/editar/', views.editar_feature, name='editar_feature'),
```

### Templates
```html
{% extends 'base.html' %}
{% block 'title' %}Título — JuriAI{% endblock %}
{% block 'content' %}
<!-- Conteúdo aqui -->
{% endblock 'content' %}
```

### Helpers de parse (já existem em usuarios/views.py)
```python
# Datas BR: _parse_date_br('15/04/2026') → date(2026, 4, 15)
# Decimais BR: _parse_decimal_br('15.000,00') → Decimal('15000.00')
```

---

## 📦 Dependências instaladas

| Pacote | Versão | Uso |
|---|---|---|
| Django | 6.x | Framework web |
| psycopg2-binary | — | PostgreSQL adapter |
| agno | 2.5.5 | Framework de agentes IA |
| django-q | — | Tasks assíncronas |
| django-axes | — | Rate limiting |
| django-auditlog | — | Auditoria de models |
| django-encrypted-model-fields | — | Criptografia de campos |
| reportlab | 4.4.10 | Geração de PDF |
| openpyxl | 3.1.5 | Geração de Excel |
| python-docx | 1.2.0 | Geração de .docx |
| requests | — | HTTP client (API DataJud, BCB) |

---

## 🚫 Regras absolutas

1. **NUNCA** alterar arquivos sem mostrar o plano antes
2. **NUNCA** fazer commit — isso é feito manualmente
3. **NUNCA** remover ou alterar código existente sem justificativa
4. **NUNCA** usar `type="date"` em inputs — usar `type="text"` com `data-mask="date"`
5. **NUNCA** usar `type="number"` para moeda — usar `type="text"` com `data-mask="currency"`
6. **NUNCA** usar `datetime.now()` — usar `django.utils.timezone.now()`
7. **NUNCA** criar views sem `@login_required` e ownership check
8. **SEMPRE** rodar `python manage.py check` após qualquer alteração
9. **SEMPRE** usar `get_object_or_404` com filtro de user para ownership
10. **SEMPRE** seguir o padrão visual existente (Tailwind, rounded-2xl, shadow-sm)
