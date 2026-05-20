# Landing Page JuriAI — Redesign Premium

**Data:** 2026-05-20
**Status:** Spec aprovada, pronta para plano de implementação
**Substitui:** `templates/home.html` (landing pública atual)

---

## 1. Contexto

O JuriAI hoje serve sua landing pública via `templates/home.html` (tema light, Cormorant Garamond + DM Sans, paleta indigo). O usuário avaliou a landing como **"pouco sofisticada"** e identificou três problemas:

1. **Falta peso visual** — paleta clara, contraste baixo, hierarquia tipográfica fraca não passam autoridade.
2. **Cara genérica de SaaS, não de jurídico** — poderia ser landing de qualquer startup; falta o ar de escritório premium (navy, dourado, fotografia clássica, gravidade).
3. **Pouco conteúdo / faltam provas e seções** — só hero, 3 agentes e CTA; não demonstra a profundidade da plataforma (calculadora judicial, processos+DataJud, financeiro, geração de documentos).

A referência de inspiração foi `https://lawyer-landing-68.aura.build/` (escritório polonês) e a versão analisada em `references/aura-landing.html`. O usuário também forneceu duas imagens próprias em `references/`:
- `law.png` — Lady Justice em bronze, gavel e livros de couro
- `books.jpg` — biblioteca clássica com bustos de filósofos

## 2. Objetivos

A nova landing deve:

- Transmitir autoridade e gravidade de escritório jurídico premium
- Demonstrar a profundidade real da plataforma (mostrar módulos além dos 3 agentes)
- Construir confiança específica para o público advogado (LGPD, segurança, controle do dado)
- Evitar qualquer sinalização de "produto de IA genérico" no copy e no visual
- Substituir a landing atual sem adicionar dependências novas (mantém Tailwind via CDN)

## 3. Não-objetivos

Não entram nesta versão:

- Testemunhos / depoimentos (não há clientes reais ainda)
- FAQ
- Tabela de pricing ou página de pricing
- Formulário de contato no hero (estilo aura.build)
- Seção dedicada de CRM ou captação via WhatsApp
- Página "Sobre", páginas de blog ou recursos
- Tradução para inglês
- Dark mode toggle (a landing já tem partes dark por design)
- Vídeo em background no hero

## 4. Decisões fechadas com o usuário

| # | Decisão | Valor escolhido |
|---|---|---|
| 1 | Direção visual | Navy + dourado + creme (combinação A + C apresentadas) |
| 2 | Densidade de cores escuras | Light dominante; 3 âncoras dark apenas |
| 3 | Layout do hero | Foto + mockup do produto sobreposto (opção C) |
| 4 | Foto do hero | `law.png` (Lady Justice) |
| 5 | Tipografia | Fraunces (display, opsz variável) + Inter (UI/body) |
| 6 | Conteúdo a incluir | Showcase profundo de produto + bloco de Trust/Segurança |
| 7 | 3º pilar do overview | Manter "Secretaria Autônoma" |
| 8 | Terminologia | Nunca usar "IA" ou "inteligência artificial"; usar "inteligência jurídica avançada" ou "inteligência avançada" |
| 9 | Pontuação | Nunca usar travessão (—) em qualquer copy |
| 10 | Arquivo | Substituir `templates/home.html` direto |

## 5. Sistema visual

### 5.1 Cores

```
Ink         #0F172A   navy/slate principal (fundos dark)
Ink-2       #0C1D3D   navy mais quente (gradientes)
Navy-700    #1E3A5F   acento em headlines light
Gold        #D4A547   acento principal (CTA, palavras-chave em itálico)
Cream       #F5EFE2   fundo principal (light)
Cream-Light #FAFAF7   alternativa ainda mais clara para seções vizinhas
Muted       #6B7A96   texto secundário em fundo dark
Faint       #2E3A52   réguas, separadores em fundo dark
Text-Light  #0F172A   texto principal em fundo claro (mesmo do Ink)
Text-Muted  #64748B   texto secundário em fundo claro
```

A paleta usa **navy menos saturado** (slate-900) em vez de azul vivo. O dourado é o único acento; nunca aparece em conjunto com outras cores quentes que conflitem.

### 5.2 Tipografia

```
Fraunces  display, opsz variável (96-144)
          weights: 400, 500, 600; italic 500
          uso: H1, H2, números grandes em stats
Inter     UI e body
          weights: 300, 400, 500, 600, 700
          uso: H3, body, captions, botões, navegação
```

Escala:

```
H1   3.4rem   Fraunces 500, opsz 144, line 1.04, letter -0.022em
H2   2.1rem   Fraunces 500, opsz 96,  line 1.08, letter -0.018em
H3   1.05rem  Inter 600, letter -0.012em
Body 0.95rem  Inter 400, line 1.65, opacity 0.85 em dark
Sub  1.02rem  Inter 400, line 1.65, opacity 0.80 em dark
Cap  0.70rem  Inter 600, letter 0.16em, uppercase, color gold
```

Padrão de palavra-chave: a segunda metade do headline vai em `Fraunces italic` com cor dourada. Exemplo: "Jurídico inteligente, *resultados reais*."

### 5.3 Componentes

**Botão primário (gold)**

```
bg #D4A547, color #0F172A, radius 8, font-weight 600
box-shadow 0 0 30px rgba(212,165,71,0.25)
hover: bg #E0B558, translateY(-1px)
```

**Botão ghost (sobre dark)**

```
bg transparent, color #F5EFE2, border 1px rgba(245,239,226,0.25), radius 8
hover: bg rgba(255,255,255,0.04), border opacity 0.4
```

**Botão sólido escuro (sobre cream)**

```
bg #0F172A, color #F5EFE2, radius 8, font-weight 600
hover: bg #0C1D3D
```

**Badge**

```
padding .32rem .8rem, radius 20px
bg rgba(212,165,71,0.12), border 1px rgba(212,165,71,0.3)
color #D4A547, font-size .65rem, letter 0.16em, uppercase
opção: dot pulsante (5px, animação pulse 2.5s)
```

**Chip (etiqueta de feature)**

```
dark:  bg rgba(245,239,226,0.08), color #F5EFE2, border rgba(245,239,226,0.15)
light: bg rgba(15,23,42,0.06), color #0F172A, border rgba(15,23,42,0.12)
font-size .70rem, padding .25rem .65rem, radius 5px
```

**Card de módulo (light)**

```
bg #FFFFFF, border 1px #E3DCC8, radius 12, shadow 0 1px 4px rgba(0,0,0,0.04)
hover: border #d4a547 (subtle), shadow 0 10px 30px rgba(15,23,42,0.06)
padding 1.5rem
```

**Mockup card (sobre hero dark)**

```
bg rgba(15,23,42,0.6), backdrop-filter blur(20px)
border 1px rgba(212,165,71,0.2), radius 10
shadow 0 20px 60px rgba(0,0,0,0.45)
header com ícone serif, título, badge gold "Risco N/100"
itens com seta dourada
```

### 5.4 Padrão de seção

- **Pretitle**: Cap (gold, uppercase)
- **Régua dourada**: barra 36×1px, gold, margem 1rem abaixo do pretitle
- **Headline**: Fraunces 500, palavra-chave em itálico dourado
- **Sub**: parágrafo curto, opacidade 0.80
- **Conteúdo**: texto à esquerda + mockup/screenshot à direita (alternando lados a cada seção para ritmo visual)

## 6. Arquitetura de informação

12 seções totais, organizadas em 4 blocos:

```
Bloco                     Seção                                    Tom
─────────────────────────────────────────────────────────────────────
ABERTURA           01    Header sticky glass                       glass
                   02    Hero (foto law.png + mockup análise)      dark ★
                   03    Stats strip (50+ tribunais · ...)         light

VISÃO GERAL        04    Três pilares (Análise · Chat · Secret.)   light

SHOWCASE           05    Análise de Documentos                     light
                   06    Calculadora Judicial                      light
                   07    Processos + DataJud + Prazos              light

MANIFESTO          08    "Tradição encontra inteligência" (books)  dark ★

SHOWCASE (cont.)   09    Financeiro + Geração de Documentos        light
                   10    Integrações (faixa fina)                  light

CONFIANÇA          11    Trust / Segurança / LGPD                  light

FECHAMENTO         12    CTA final + Footer integrado              dark ★
─────────────────────────────────────────────────────────────────────
★ = âncora dark (3 no total)
```

### 6.1 Detalhamento por seção

#### 01 — Header sticky glass

- Background `rgba(255,255,255,0.94)` + `backdrop-filter: blur(14px)`
- Sticky no topo, border-bottom hairline
- Logo "Juri**AI**" (segundo "AI" em gold, italic Fraunces 500)
- Nav: Funcionalidades · Segurança · Entrar
- CTA "Começar grátis →" (botão sólido escuro)
- Mobile: hamburger expande menu vertical com links em Fraunces italic

#### 02 — Hero (dark, âncora 1)

Estrutura empilhada centralizada:

1. Badge: "● Plataforma de inteligência jurídica" (dot pulsante gold)
2. H1: "Jurídico inteligente, *resultados reais.*"
3. Sub: "Documentos, processos, agenda e atendimento em um único ambiente. Inteligência avançada que apoia o julgamento do advogado sem jamais substituí-lo."
4. CTAs: "Começar grátis →" (gold) + "▸ Ver demonstração" (ghost)
5. Mockup card sobreposto: simula análise de risco
   - Header: ícone § + "Petição inicial · Silva vs Construtora" + badge "Risco 28/100"
   - 3 itens com pin dourado, conteúdo plausível citando Art. 523 CPC e STJ Tema 1.061
6. Stats inline: "50+ Tribunais · DataJud Integrado · 24/7 Atendimento"

Background: `law.png` com:
- Crop centralizado focando a balança da Lady Justice
- Overlay duplo: gradiente vertical (transparent→navy 95%) + lateral (navy 70%→25%→70%)
- Grain overlay SVG (~6% opacity, fractal noise)
- Animação leve `pulse 10s` no scale da imagem

#### 03 — Stats strip (light)

Faixa cream com 3 stats em colunas iguais separadas por hairline:

```
[ícone gold]  3 agentes jurídicos especializados
              JuriAI · SecretariaAI · JurisprudênciaAI

[ícone gold]  Análise jurisprudencial em segundos
              Índice de risco e red flags automáticos

[ícone gold]  Atendimento autônomo 24/7
              WhatsApp e Google Calendar integrados
```

#### 04 — Três pilares (light)

Pretitle "Capacidades". Headline "Três pilares, um ambiente."

Grid 3 colunas com cards 3:4 (estilo aura): cada card com pequena ilustração ou ícone dourado no topo, título Fraunces italic embaixo, descrição em 2 linhas:

1. **Análise de Documentos.** Identifica riscos, inconsistências e red flags antes do protocolo.
2. **Chat por Cliente.** Cada cliente tem seu próprio assistente treinado com os documentos do caso.
3. **Secretaria Autônoma.** Atende, agenda e mantém a comunicação fluindo sem intervenção humana.

#### 05 — Análise de Documentos (light)

Layout texto-esquerda / mockup-direita. Pretitle "Módulo 01". Headline: "Risco identificado *antes do protocolo.*"

Sub e bullets cobrindo: OCR automático, índice de risco 0-100, red flags por categoria (prazo, jurisprudência, formatação), suporte a PDF/DOCX/imagem.

Mockup: replica da página de análise com índice de risco grande, lista de red flags, botão "Reanalisar".

Chips inferiores: PDF · DOCX · OCR · Petições · Contratos · Pareceres.

#### 06 — Calculadora Judicial (light)

Layout mockup-esquerda / texto-direita (inverte). Pretitle "Módulo 02". Headline: "Cálculos prontos *para protocolo.*"

Sub e bullets cobrindo: índices oficiais (IPCA-E, INPC, SELIC, TR, IGP-M, Taxa Legal), juros simples e compostos, multa Art. 523 CPC, honorários sucumbenciais 10-20%, tabelas específicas dos TJs (SP, RJ, MG, PR, RS, CJF, TST), comparador de cenários.

Mockup: tabela mês a mês com correção, juros, subtotal; total destacado em gold; mini-gráfico de evolução.

#### 07 — Processos + DataJud + Prazos (light)

Layout texto-esquerda / mockup-direita. Pretitle "Módulo 03". Headline: "Cada processo *sempre atualizado.*"

Sub e bullets cobrindo: integração DataJud (consulta automática diária), timeline de andamentos, prazos com alerta por email, sincronização bidirecional com Google Calendar, suporte a todos os tribunais brasileiros.

Mockup: timeline vertical de andamentos com dots coloridos por fonte (DataJud azul, Manual cinza) + mini calendário com prazos destacados.

#### 08 — Manifesto (dark, âncora 2)

Background: `books.jpg` (biblioteca, bustos, livros encadernados) com:
- Overlay lateral duplo (escuro nas bordas, mais transparente no centro)
- Grain overlay 6%
- Sem parallax na primeira versão (adicionar depois se justificado)

Conteúdo centralizado:
- Régua dourada
- Headline H2: "Tradição que pensa, *inteligência que age.*"
- Parágrafo curto: "Cada decisão jurídica nasce sobre séculos de doutrina. O JuriAI torna esse acervo, e o seu próprio, instantaneamente acessível. O julgamento continua seu."

Sem CTA. Funciona como respiro narrativo e palimpsesto entre os blocos de showcase.

#### 09 — Financeiro + Geração de Documentos (light)

Layout 2 colunas igualitárias com mini-cards (não é o padrão texto+mockup). Pretitle "Módulos 04 + 05".

Coluna 1. **Financeiro**
- Headline: "Receita visível, *inadimplência controlada.*"
- Bullets: honorários (fixo/êxito/hora/mensalidade), pagamentos parciais, fluxo de caixa, alerta de inadimplência via WhatsApp, exportação PDF/Excel.
- Mockup compacto: dashboard com 3 cards de KPI (Receita do mês, A receber, Em atraso).

Coluna 2. **Geração de Documentos**
- Headline: "Petições e contratos *em minutos.*"
- Bullets: templates editáveis, agente RedacaoAI especializado em redação jurídica brasileira, variáveis automáticas (cliente, processo, data), exportação .docx e .pdf prontos para protocolo.
- Mockup compacto: editor com preview side-by-side.

#### 10 — Integrações (light, faixa fina)

Padding vertical menor (~3rem). Pretitle "Integrado com o que você já usa". Linha horizontal de 4-5 logos em tom mais discreto (grayscale com hover colorido):

`DataJud · Google Calendar · WhatsApp · Stripe · OpenAI*`

*OpenAI aparece como infra, sem alarde. Pode ser substituído por marca neutra ("Modelos avançados") se o "IA" estiver banido até em logo. Decisão final fica no plano de implementação.

#### 11 — Trust / Segurança / LGPD (light)

Pretitle "Confiança". Headline H2: "Seus dados, *seu controle.*"

Sub curto: "Construído desde o primeiro dia para advogados que levam dados de clientes a sério."

Grid 4 cards com ícone gold no topo:

1. **Dados criptografados.** Em trânsito e em repouso, com chave gerenciada pelo escritório.
2. **LGPD nativo.** Consentimento auditado, exclusão de conta completa, exportação de dados.
3. **Auditoria completa.** Cada alteração em cliente, processo ou documento fica registrada e visível.
4. **Isolamento por cliente.** Cada cliente tem seu próprio espaço de busca. Nada vaza entre casos.

Card destaque inferior: "Plataforma 100% brasileira, infraestrutura no Brasil, suporte em português."

#### 12 — CTA final + Footer (dark, âncora 3)

CTA centralizado:
- Pequena badge "Comece grátis"
- H2: "Pronto para trabalhar *diferente?*"
- Sub: "Crie sua conta. Sem cartão de crédito."
- Botão gold grande "Criar conta gratuita →"
- Linha de trust inline: "Dados criptografados · Configuração em minutos · Suporte em português"

Background dark com glow indigo discreto nos cantos (estilo aura form), grain 6%.

Footer integrado abaixo (não é seção separada):
- Logo "Juri**AI**" + tagline "Plataforma de inteligência jurídica"
- 3 colunas: Sitemap (Funcionalidades, Segurança, Entrar) · Resources (Privacidade, Termos) · Contato (email, social)
- Linha final: © 2026 JuriAI · Todos os direitos reservados

## 7. Fotografia e assets

| Asset | Localização | Uso |
|---|---|---|
| `law.png` | `references/` → mover para `static/landing/` | Hero (seção 02) |
| `books.jpg` | `references/` → mover para `static/landing/` | Manifesto (seção 08) |
| Mockups dos módulos | Render via HTML/CSS dentro do template | Seções 02, 05, 06, 07, 09 |
| Logos de integração | SVG inline ou pasta dedicada | Seção 10 |

**Não usar** outras fotografias humanas (advogados, equipes, escritórios) — quebra a coerência simbólica e parece stock genérico.

**Mockups de produto** são representações HTML/CSS, não capturas reais. Conteúdo plausível mas fictício: nomes ("Silva vs Construtora"), números (R$ 47.320,00), datas, citações jurídicas verossímeis (Art. 523 CPC, STJ Tema 1.061).

## 8. Diretrizes de copy

**Banidas em todo copy da landing:**

- "IA", "inteligência artificial", "AI", "artificial intelligence"
- Travessão (—) em qualquer contexto
- "Não é apenas X, é Y"
- Hedge verbs: "pode ajudar", "permite que", "viabiliza", "potencializa"
- Clichês: "robusto", "alavancar", "delve", "tapestry"
- Bullets dentro de parágrafos correntes
- Tríades obrigatórias (sempre 3 itens) — usar 2, 3 ou 4 conforme o conteúdo pede

**Preferidas:**

- "Inteligência jurídica avançada" / "inteligência avançada"
- Frases curtas e declarativas
- Pontuação simples: ponto, vírgula, dois-pontos, parênteses
- Verbos de ação concretos: identifica, calcula, gera, atualiza
- Tom: confiante, técnico, sem hype

**Padrão de headline de seção:**
Fórmula `[Substantivo concreto], *[verbo/qualidade em itálico].*`

Exemplos:
- "Risco identificado *antes do protocolo.*"
- "Cálculos prontos *para protocolo.*"
- "Cada processo *sempre atualizado.*"
- "Receita visível, *inadimplência controlada.*"
- "Tradição que pensa, *inteligência que age.*"

## 9. Animação e interação

- **Glass nav**: blur(14px) + opacity transition em scroll (mais sólido após 100px)
- **Underline anim** nos links de nav: width 0→100% em hover (200ms ease-out)
- **Reveal on scroll**: IntersectionObserver dispara classe `.is-visible` em cada seção; transição `opacity 0→1` + `translateY 20px→0` em 800ms cubic-bezier(0.16, 1, 0.3, 1). Sem bibliotecas externas.
- **Botão gold**: glow base 0 0 30px gold/25%, hover aumenta para 40% + translateY(-1px)
- **Hero pulse**: foto bg com `animation: pulse 10s alternate infinite` (scale 1 ↔ 1.03)
- **Mockup card no hero**: leve `box-shadow` pulsando para chamar atenção (opcional, decisão na implementação)
- **Cards de módulo**: hover muda borda para `#d4a547` opacidade 0.3 + shadow elevation
- **Grain overlay**: estático, SVG inline em base64, opacity 6-8% nas seções dark

## 10. Aspectos técnicos

**Stack (sem mudanças):**
- Tailwind CSS via CDN (igual hoje)
- Google Fonts: Fraunces (opsz variável 9..144, weights 400/500/600 + italic 500) + Inter (300, 400, 500, 600, 700)
- Iconify ou SVG inline para ícones
- Vanilla JS para nav scroll state, reveal on scroll, glass effect

**Estrutura HTML:**
- Template Django `templates/home.html` (sobrescreve o atual)
- Variáveis Django mantidas: `{% url 'login' %}`, `{% url 'cadastro' %}`, `{% static %}` para `law.png` e `books.jpg`
- Acessibilidade: alt text descritivo nas imagens, `aria-label` no header e nav, contraste WCAG AA mínimo em todos os textos

**Imagens estáticas:**
- Mover `references/law.png` e `references/books.jpg` para `static/landing/`
- Adicionar versões otimizadas (webp + fallback jpg/png) se for crítico para performance
- Lazy loading nas imagens fora do viewport inicial

**Performance:**
- Tailwind CDN ainda é aceitável para landing (compilar para build de produção fica em backlog separado)
- Fontes via Google Fonts com `display=swap`
- Imagens otimizadas (target: hero <300KB, books <250KB)

**Responsivo:**
- Mobile-first: hero stack vertical, nav vira hamburger, mockup card abaixo do CTA
- Breakpoints: sm 640, md 768, lg 1024, xl 1280 (Tailwind padrão)
- Em mobile: showcase de módulos vira coluna única, mockups abaixo do texto

## 11. Migração

1. Salvar `templates/home.html` atual como `templates/legacy/home_pre_2026_05.html` (ou deletar — decisão final do usuário no momento da merge).
2. `templates/preview_landing.html` e `templates/preview_landing_light.html` podem ser deletados ou movidos para `legacy/`.
3. Substituir `templates/home.html` pela nova versão.
4. Adicionar `law.png` e `books.jpg` em `static/landing/` e referenciar via `{% static %}`.
5. Validar localmente com `python manage.py runserver`.
6. Conferir que links `{% url 'login' %}` e `{% url 'cadastro' %}` continuam funcionando.

Sem migrations de banco. Sem mudanças em views ou URLs. Sem dependências novas no `requirements.txt`.

## 12. Critérios de pronto

A landing está pronta quando:

- [ ] Todas as 12 seções implementadas conforme a arquitetura
- [ ] `law.png` no hero, `books.jpg` no manifesto, ambos via `{% static %}`
- [ ] Nenhuma ocorrência de "IA", "inteligência artificial", travessão no copy
- [ ] Paleta navy + dourado + creme aplicada via CSS variables
- [ ] Tipografia Fraunces + Inter carregando do Google Fonts
- [ ] 3 âncoras dark (hero, manifesto, CTA) com grain overlay
- [ ] Mockups de produto renderizados em HTML/CSS, não imagens
- [ ] Reveal on scroll funcionando em todas as seções
- [ ] Glass nav com blur funcionando em scroll
- [ ] Responsivo: mobile, tablet, desktop testados
- [ ] Lighthouse: Performance ≥ 85, Acessibilidade ≥ 95, Best Practices ≥ 95

## 13. Questões em aberto para o plano de implementação

- Logo da OpenAI na seção 10: usar logo real ou substituir por marca neutra?
- `webp` é obrigatório ou jpg/png aceitáveis na v1?
- Animação de pulse do hero deve estar ativa em prefers-reduced-motion? (resposta: não)
- Compilação local do Tailwind agora ou fica em backlog?

Estas decisões podem ser respondidas durante o plano de implementação (skill `writing-plans`) ou no momento de codar.
