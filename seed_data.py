"""
Script de dados fictícios para o usuário teste2.
Execute: python seed_data.py (a partir da raiz do projeto)
"""
import os
import sys
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from usuarios.models import Cliente, Documentos
from ia.models import Pergunta, ContextRag, AnaliseJurisprudencia

# ─── Usuário alvo ─────────────────────────────────────────────────────────────
try:
    user = User.objects.get(username='teste2')
except User.DoesNotExist:
    print("ERRO: usuário 'teste2' não encontrado. Crie-o antes de rodar este script.")
    sys.exit(1)

# Limpa dados anteriores do teste2 para idempotência
Cliente.objects.filter(user=user).delete()
print("Dados anteriores do teste2 removidos.")

# ─── 1. CLIENTES ──────────────────────────────────────────────────────────────
clientes_data = [
    # Pessoas Físicas — ativas
    {"nome": "João Carlos Ferreira",       "email": "joao.ferreira@gmail.com",        "tipo": "PF", "status": True},
    {"nome": "Maria Aparecida Santos",     "email": "maria.santos@outlook.com",        "tipo": "PF", "status": True},
    {"nome": "Pedro Henrique Oliveira",    "email": "pedro.oliveira@hotmail.com",      "tipo": "PF", "status": True},
    {"nome": "Ana Paula Rodrigues",        "email": "ana.rodrigues@gmail.com",         "tipo": "PF", "status": True},
    {"nome": "Carlos Eduardo Lima",        "email": "carlos.lima@gmail.com",           "tipo": "PF", "status": True},
    {"nome": "Fernanda Costa Almeida",     "email": "fernanda.almeida@email.com",      "tipo": "PF", "status": True},
    {"nome": "Rafael Martins Souza",       "email": "rafael.souza@gmail.com",          "tipo": "PF", "status": True},
    # Pessoas Físicas — inativas
    {"nome": "Luciana Pereira Barbosa",    "email": "luciana.barbosa@yahoo.com.br",    "tipo": "PF", "status": False},
    {"nome": "Marcos Antônio Vieira",      "email": "marcos.vieira@hotmail.com",       "tipo": "PF", "status": False},
    # Pessoas Jurídicas — ativas
    {"nome": "Construtora Horizonte Ltda.",  "email": "juridico@horizonte.com.br",     "tipo": "PJ", "status": True},
    {"nome": "TechBrasil Soluções S.A.",     "email": "contato@techbrasil.com.br",     "tipo": "PJ", "status": True},
    {"nome": "Grupo Medicenter Saúde",       "email": "adm@medicenter.com.br",         "tipo": "PJ", "status": True},
    # Pessoa Jurídica — inativa
    {"nome": "Agropecuária São Jorge Ltda.", "email": "juridico@saojorge.agr.br",      "tipo": "PJ", "status": False},
]

clientes = []
for d in clientes_data:
    c = Cliente.objects.create(user=user, **d)
    clientes.append(c)

print(f"  → {len(clientes)} clientes criados")

# ─── 2. DOCUMENTOS ────────────────────────────────────────────────────────────
tipos_doc = [
    ("C",    "contrato"),
    ("P",    "peticao"),
    ("CONT", "contestacao"),
    ("R",    "recurso"),
    ("O",    "outro"),
]

def slug(nome):
    import unicodedata, re
    s = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

def markdown_peticao(cliente_nome, tipo_label, data_str):
    return f"""# {tipo_label.upper()} — {cliente_nome}

**Data:** {data_str}
**Processo nº:** 0{hash(cliente_nome + tipo_label) % 9000000 + 1000000}-{hash(tipo_label) % 90 + 10}.2024.8.26.0100
**Vara:** 3ª Vara Cível da Comarca de São Paulo
**Autor:** {cliente_nome}
**Réu:** [Parte contrária]

---

## I. DOS FATOS

O requerente, {cliente_nome}, vem perante V. Exa. expor e requerer o que segue.

Em {data_str}, o requerente firmou contrato com a parte contrária para prestação de serviços
no valor de R$ {abs(hash(cliente_nome)) % 50000 + 5000:,.2f} (reais), com prazo de entrega de 90 dias.

Ocorre que a parte contrária deixou de cumprir as obrigações contratuais pactuadas,
causando prejuízos materiais e morais ao requerente, conforme documentos anexos.

Apesar das notificações extrajudiciais enviadas em 15/01/2024 e 02/03/2024,
a parte contrária permaneceu inerte, ensejando a propositura da presente ação.

## II. DO DIREITO

A conduta da parte contrária configura inadimplemento contratual nos termos dos
artigos 389 e 395 do Código Civil Brasileiro (Lei nº 10.406/2002).

Nos termos do art. 927 do CC, *"aquele que, por ato ilícito (arts. 186 e 187),
causar dano a outrem, fica obrigado a repará-lo"*.

Ademais, aplicam-se ao caso as disposições do Código de Defesa do Consumidor
(Lei nº 8.078/90), em especial o art. 14, que prevê a responsabilidade objetiva
do fornecedor pelos danos causados aos consumidores.

### 2.1 Do Dano Material

Os prejuízos materiais comprovados totalizam R$ {abs(hash(cliente_nome + 'mat')) % 30000 + 3000:,.2f},
conforme notas fiscais e recibos em anexo.

### 2.2 Do Dano Moral

O descumprimento contratual gerou angústia, frustração e abalo psicológico ao
requerente, configurando dano moral indenizável, a ser arbitrado por V. Exa.

## III. DOS PEDIDOS

Ante o exposto, requer-se:

a) A procedência da presente ação;
b) A condenação da parte contrária ao pagamento de danos materiais no valor de
   R$ {abs(hash(cliente_nome + 'mat')) % 30000 + 3000:,.2f};
c) A condenação ao pagamento de danos morais a ser arbitrado por V. Exa.;
d) A condenação ao pagamento de custas processuais e honorários advocatícios
   de 20% sobre o valor da condenação;
e) A concessão dos benefícios da justiça gratuita, caso necessário.

## IV. DAS PROVAS

Protesta-se pela produção de todos os meios de prova em direito admitidos,
especialmente documental, testemunhal e pericial.

---

**Valor da causa:** R$ {abs(hash(cliente_nome + 'causa')) % 80000 + 10000:,.2f}

São Paulo, {data_str}.

**[Nome do Advogado]**
OAB/SP nº 123.456
"""

def markdown_contrato(cliente_nome, data_str):
    return f"""# CONTRATO DE PRESTAÇÃO DE SERVIÇOS JURÍDICOS

**Contratante:** {cliente_nome}
**Contratado:** Escritório de Advocacia [Nome]
**Data:** {data_str}

---

## CLÁUSULA 1ª — DO OBJETO

O presente contrato tem por objeto a prestação de serviços advocatícios pelo
CONTRATADO ao CONTRATANTE, especificamente:

- Representação judicial e extrajudicial;
- Elaboração de petições, recursos e demais peças processuais;
- Acompanhamento de processos administrativos e judiciais;
- Consultoria jurídica preventiva.

## CLÁUSULA 2ª — DOS HONORÁRIOS

Os honorários advocatícios são fixados em R$ {abs(hash(cliente_nome + 'hon')) % 8000 + 2000:,.2f}
mensais, devidos até o dia 5 de cada mês.

## CLÁUSULA 3ª — DO PRAZO

O presente contrato vigorará pelo prazo de 12 (doze) meses, podendo ser
renovado mediante instrumento aditivo firmado pelas partes.

## CLÁUSULA 4ª — DA RESCISÃO

O presente contrato poderá ser rescindido por qualquer das partes mediante
notificação escrita com antecedência mínima de 30 (trinta) dias.

## CLÁUSULA 5ª — DO FORO

Fica eleito o Foro da Comarca de São Paulo para dirimir quaisquer controvérsias
oriundas do presente instrumento.

---

**{cliente_nome}**
CPF/CNPJ: {abs(hash(cliente_nome)) % 900000000000 + 100000000000}

**[Nome do Advogado]**
OAB/SP nº 123.456

São Paulo, {data_str}.
"""

documentos_criados = []
now = timezone.now()

for i, cliente in enumerate(clientes):
    nome_slug = slug(cliente.nome)
    # Documento 1
    tipo1, tipo1_label = tipos_doc[i % len(tipos_doc)]
    data1 = now - timedelta(days=60 + i * 3)
    data1_str = data1.strftime("%d/%m/%Y")
    content1 = markdown_peticao(cliente.nome, tipo1_label, data1_str)
    doc1 = Documentos.objects.create(
        cliente=cliente,
        tipo=tipo1,
        arquivo=f"documentos/{tipo1_label}_{nome_slug}.pdf",
        data_upload=data1,
        content=content1,
    )
    documentos_criados.append(doc1)

    # Documento 2
    tipo2, tipo2_label = tipos_doc[(i + 2) % len(tipos_doc)]
    data2 = now - timedelta(days=30 + i * 2)
    data2_str = data2.strftime("%d/%m/%Y")
    content2 = markdown_contrato(cliente.nome, data2_str)
    doc2 = Documentos.objects.create(
        cliente=cliente,
        tipo=tipo2,
        arquivo=f"documentos/{tipo2_label}_{nome_slug}_2.pdf",
        data_upload=data2,
        content=content2,
    )
    documentos_criados.append(doc2)

print(f"  → {len(documentos_criados)} documentos criados")

# ─── 3. ANÁLISES DE JURISPRUDÊNCIA ────────────────────────────────────────────
analises_data = [
    {
        "doc_index": 0,  # João Carlos Ferreira — doc 1
        "indice_risco": 88,
        "classificacao": "Crítico",
        "erros_coerencia": [
            "Contradição entre o valor declarado na exordial (§ 2º) e os documentos em anexo",
            "Datas inconsistentes nas notificações extrajudiciais mencionadas",
        ],
        "riscos_juridicos": [
            "Prazo prescricional bienal em risco — art. 206, § 3º, V do CC",
            "Ausência de comprovação de dano moral efetivo — entendimento sumulado do STJ",
            "Pedido genérico de danos morais sem quantificação mínima",
        ],
        "problemas_formatacao": [
            "Endereçamento incorreto — omitida a vara e o juízo competente",
            "Falta de numeração nas folhas",
        ],
        "red_flags": [
            "Ausência de fundamentação legal para pedido de tutela de urgência",
            "Valor da causa subdimensionado em relação aos pedidos formulados",
            "Competência territorial questionável — endereço da parte contrária em outro estado",
        ],
    },
    {
        "doc_index": 4,  # Carlos Eduardo Lima — doc 1
        "indice_risco": 82,
        "classificacao": "Crítico",
        "erros_coerencia": [
            "Qualificação da parte contrária incompleta — falta CNPJ",
            "Referência a cláusula contratual inexistente no instrumento anexado",
        ],
        "riscos_juridicos": [
            "Litispendência potencial com processo nº 0012345-2023 na mesma vara",
            "Ausência de tentativa de conciliação prévia exigida pelo CPC, art. 334",
        ],
        "problemas_formatacao": [
            "Petição excede limite de páginas do regimento interno do TJSP",
        ],
        "red_flags": [
            "Prazo prescricional em risco — menos de 30 dias para extinção",
            "Ausência de procuração nos autos",
            "Pedido de antecipação de tutela sem demonstração do periculum in mora",
        ],
    },
    {
        "doc_index": 8,  # Marcos Antônio Vieira — doc 1
        "indice_risco": 74,
        "classificacao": "Alto",
        "erros_coerencia": [
            "Fundamentação jurídica desatualizada — artigo revogado pela Lei nº 14.195/2021",
        ],
        "riscos_juridicos": [
            "Honorários advocatícios estipulados abaixo do mínimo tabela OAB",
            "Cálculo de correção monetária com índice incorreto (INPC ao invés de IPCA-E)",
        ],
        "problemas_formatacao": [
            "Assinatura digital não validada no sistema e-SAJ",
            "Ausência de índice/sumário para peça com mais de 30 páginas",
        ],
        "red_flags": [
            "Jurisprudência citada diverge do entendimento atual do STJ (Tema 1.076)",
            "Valor dos juros moratórios em desacordo com a Selic vigente",
        ],
    },
    {
        "doc_index": 14,  # TechBrasil Soluções S.A. — doc 1
        "indice_risco": 69,
        "classificacao": "Alto",
        "erros_coerencia": [
            "Cláusula de vigência apresenta redação ambígua quanto ao término automático",
            "Multa rescisória definida em percentual sobre valor não especificado",
        ],
        "riscos_juridicos": [
            "Cláusula penal potencialmente abusiva — passível de revisão judicial (art. 413 CC)",
            "Ausência de cláusula de eleição de foro para contratos com consumidor",
        ],
        "problemas_formatacao": [
            "Contrato sem rubrica em todas as páginas",
        ],
        "red_flags": [
            "Cláusula de não-concorrência sem limitação temporal — nulidade potencial",
        ],
    },
    {
        "doc_index": 20,  # Grupo Medicenter Saúde — doc 1
        "indice_risco": 58,
        "classificacao": "Médio",
        "erros_coerencia": [
            "Referência ao prazo de resposta diverge entre corpo do texto e cabeçalho",
        ],
        "riscos_juridicos": [
            "Ausência de menção à Lei Geral de Proteção de Dados (LGPD) em cláusula de privacidade",
        ],
        "problemas_formatacao": [
            "Formatação de citações fora do padrão ABNT exigido pelo juízo",
            "Número de processo no cabeçalho difere do corpo do texto",
        ],
        "red_flags": [
            "Pedido alternativo não fundamentado adequadamente",
        ],
    },
]

analises_criadas = []
for a in analises_data:
    doc = documentos_criados[a["doc_index"]]
    analise = AnaliseJurisprudencia.objects.create(
        documento=doc,
        indice_risco=a["indice_risco"],
        classificacao=a["classificacao"],
        erros_coerencia=a["erros_coerencia"],
        riscos_juridicos=a["riscos_juridicos"],
        problemas_formatacao=a["problemas_formatacao"],
        red_flags=a["red_flags"],
        tempo_processamento=12 + len(analises_criadas) * 3,
    )
    analises_criadas.append(analise)

print(f"  → {len(analises_criadas)} análises de jurisprudência criadas")

# ─── 4. PERGUNTAS (histórico de chat com JuriAI) ──────────────────────────────
perguntas_data = [
    # João Carlos Ferreira
    ("Qual o prazo para entrar com recurso de apelação após a sentença?", 0),
    ("O que é o princípio da sucumbência e como ele afeta meu caso?", 0),
    # Maria Aparecida Santos
    ("Quais documentos preciso reunir para uma ação de indenização por dano moral?", 1),
    ("É possível negociar um acordo antes da audiência de conciliação?", 1),
    # Pedro Henrique Oliveira
    ("Como funciona a execução de sentença quando o devedor não paga voluntariamente?", 2),
    # Ana Paula Rodrigues
    ("O que é tutela antecipada e em que situações posso pedir?", 3),
    ("Meu contrato tem cláusula abusiva — como contestá-la judicialmente?", 3),
    # Carlos Eduardo Lima
    ("Quais são os requisitos para reconhecer prescrição intercorrente?", 4),
    # Construtora Horizonte Ltda.
    ("Quais são as obrigações da empresa em caso de rescisão imotivada de contrato de obra?", 9),
    ("Como calcular a multa rescisória prevista em contrato de empreitada?", 9),
    # TechBrasil Soluções S.A.
    ("A cláusula de não-concorrência no meu contrato é válida? Por quanto tempo pode valer?", 10),
    # Grupo Medicenter Saúde
    ("Quais são as responsabilidades jurídicas em caso de vazamento de dados de pacientes?", 11),
    ("A LGPD se aplica a clínicas médicas de pequeno porte?", 11),
]

perguntas_criadas = []
for texto, cliente_idx in perguntas_data:
    p = Pergunta.objects.create(
        pergunta=texto,
        cliente=clientes[cliente_idx],
    )
    perguntas_criadas.append(p)

    # ContextRag simulado para cada pergunta
    ContextRag.objects.create(
        pergunta=p,
        tool_name="search_knowledge",
        tool_args={"query": texto[:60], "num_documents": 3},
        content={
            "chunks": [
                {
                    "text": f"Trecho relevante do documento de {clientes[cliente_idx].nome} relacionado à consulta.",
                    "score": round(0.75 + (len(texto) % 20) / 100, 3),
                    "metadata": {"cliente_id": clientes[cliente_idx].id, "tipo": "P"},
                }
            ]
        },
    )

print(f"  → {len(perguntas_criadas)} perguntas criadas (+ {len(perguntas_criadas)} registros ContextRag)")

# ─── RESUMO ───────────────────────────────────────────────────────────────────
print()
print("=" * 50)
print("SEED CONCLUÍDO")
print("=" * 50)
print(f"  Clientes          : {Cliente.objects.filter(user=user).count()}")
print(f"  Documentos        : {Documentos.objects.filter(cliente__user=user).count()}")
print(f"  Análises          : {AnaliseJurisprudencia.objects.filter(documento__cliente__user=user).count()}")
print(f"  Perguntas (chat)  : {Pergunta.objects.filter(cliente__user=user).count()}")
print(f"  ContextRag        : {ContextRag.objects.filter(pergunta__cliente__user=user).count()}")
print("=" * 50)
