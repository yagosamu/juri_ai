# Landing Page JuriAI: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **REQUIRED IMPLEMENTATION SKILLS:** Invoke `frontend-design` and `ui-ux-pro-max` at the start of implementation (Task 1) and consult them whenever a section needs visual polish, component reference, or copy refinement. The user explicitly requested both skills be used for this build.

**Goal:** Replace `templates/home.html` with a premium, navy + gold + cream landing page that demonstrates the depth of the JuriAI platform across 12 sections (3 dark anchors + 9 light), per the spec at `docs/superpowers/specs/2026-05-20-landing-juriai-design.md`.

**Architecture:** Single Django template (`templates/home.html`) served by the existing `home` view (`usuarios/views.py:205`). All CSS inline in `<style>`, all JS inline at end of `<body>`. Images served from `templates/static/landing/`. Mobile-first responsive. Tailwind CDN (existing) plus Google Fonts (Fraunces variable + Inter). No backend changes, no new dependencies.

**Tech Stack:**
- Django 5.x (existing)
- Tailwind CSS via CDN (existing)
- Google Fonts: Fraunces (`opsz` 9..144, weights 400/500/600 + italic 500) and Inter (300/400/500/600/700)
- Vanilla JS, IntersectionObserver API, no libraries
- Whitenoise for static files (existing)

**Reference materials (open while building):**
- Spec: `docs/superpowers/specs/2026-05-20-landing-juriai-design.md`
- Inspiration HTML: `references/aura-landing.html`
- Source images: `references/law.png`, `references/books.jpg`

---

## File Structure

```
templates/home.html                        REPLACED      Main landing (single file, ~1500 lines)
templates/legacy/                          CREATED       Archive directory
templates/legacy/home_pre_2026_05.html     MOVED FROM    templates/home.html (the current one)
templates/legacy/preview_landing.html      MOVED FROM    templates/preview_landing.html
templates/legacy/preview_landing_light.html MOVED FROM   templates/preview_landing_light.html
templates/static/landing/                  CREATED       Image asset directory
templates/static/landing/law.png           COPIED FROM   references/law.png
templates/static/landing/books.jpg         COPIED FROM   references/books.jpg
```

`STATICFILES_DIRS` is `('templates/static',)` in `core/settings.py:175` — images go under `templates/static/landing/` and are referenced as `{% static 'landing/law.png' %}`.

The HTML file is large but cohesive (one landing = one file). Splitting into Django includes is out of scope; the current `home.html` already follows the single-file pattern. Sections inside the file are clearly delimited with comment banners.

---

## Verification Pattern for HTML/CSS Tasks

This project is a static landing page. Traditional unit tests do not apply. Replace the TDD loop with **visual verification**:

1. Write or change HTML/CSS/JS
2. Run `python manage.py runserver`
3. Open `http://localhost:8000/` in a browser
4. Verify the section renders correctly, no console errors, no layout breaks at 375px/768px/1280px widths
5. Commit

For JS interactions (reveal-on-scroll, glass nav), also verify the behavior (scroll the page, click the menu, etc.).

If you need visual polish guidance during a task, invoke `ui-ux-pro-max` with the section name and copy from the spec.

---

## Task 0: Asset and Template Preparation

**Files:**
- Create: `templates/legacy/` (directory)
- Create: `templates/static/landing/` (directory)
- Move: `templates/home.html` → `templates/legacy/home_pre_2026_05.html`
- Move: `templates/preview_landing.html` → `templates/legacy/preview_landing.html`
- Move: `templates/preview_landing_light.html` → `templates/legacy/preview_landing_light.html`
- Copy: `references/law.png` → `templates/static/landing/law.png`
- Copy: `references/books.jpg` → `templates/static/landing/books.jpg`

- [ ] **Step 1: Confirm Django static config**

Read `core/settings.py:174-177` and confirm `STATICFILES_DIRS = (os.path.join(BASE_DIR, 'templates/static'),)`. If it differs, stop and ask before continuing.

- [ ] **Step 2: Create archive and static directories**

```bash
mkdir -p templates/legacy
mkdir -p templates/static/landing
```

- [ ] **Step 3: Archive existing landing templates**

```bash
git mv templates/home.html templates/legacy/home_pre_2026_05.html
git mv templates/preview_landing.html templates/legacy/preview_landing.html
git mv templates/preview_landing_light.html templates/legacy/preview_landing_light.html
```

- [ ] **Step 4: Copy reference images into static**

```bash
cp references/law.png templates/static/landing/law.png
cp references/books.jpg templates/static/landing/books.jpg
```

- [ ] **Step 5: Verify Django startup still works**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add templates/legacy templates/static/landing
git commit -m "chore(landing): archive old templates and stage redesign assets"
```

---

## Task 1: Invoke design skills and create base scaffold

**Files:**
- Create: `templates/home.html` (new, replaces the archived one)

- [ ] **Step 1: Invoke ui-ux-pro-max for context**

```
Skill: ui-ux-pro-max
Args: review the spec at docs/superpowers/specs/2026-05-20-landing-juriai-design.md and prepare to assist with the JuriAI landing build (navy + gold + cream, Fraunces + Inter, 12 sections, 3 dark anchors)
```

- [ ] **Step 2: Invoke frontend-design for context**

```
Skill: frontend-design
Args: review the spec at docs/superpowers/specs/2026-05-20-landing-juriai-design.md and prepare to generate component HTML/CSS as needed
```

- [ ] **Step 3: Create new home.html with base scaffold**

Write to `templates/home.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JuriAI · Plataforma de inteligência jurídica</title>
  <meta name="description" content="Documentos, processos, agenda e atendimento em um único ambiente. Inteligência avançada que apoia o julgamento do advogado sem jamais substituí-lo.">

  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,ital,wght@9..144,0,400;9..144,0,500;9..144,0,600;9..144,1,500&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root {
      /* Cores (do spec, seção 5.1) */
      --ink:         #0F172A;
      --ink-2:       #0C1D3D;
      --navy-700:    #1E3A5F;
      --gold:        #D4A547;
      --gold-hover:  #E0B558;
      --cream:       #F5EFE2;
      --cream-light: #FAFAF7;
      --muted:       #6B7A96;
      --faint:       #2E3A52;
      --text-light:  #0F172A;
      --text-muted:  #64748B;
    }

    *, *::before, *::after { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--cream-light);
      color: var(--text-light);
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }
    .serif { font-family: 'Fraunces', Georgia, serif; font-variation-settings: "opsz" 144; }
    .serif em { font-style: italic; }

    /* Grain texture reusable on dark sections */
    .grain::after {
      content: ''; position: absolute; inset: 0; opacity: 0.07; pointer-events: none;
      background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--cream-light); }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }

    /* Reveal on scroll baseline */
    .reveal { opacity: 0; transform: translateY(20px); transition: opacity 800ms cubic-bezier(0.16,1,0.3,1), transform 800ms cubic-bezier(0.16,1,0.3,1); }
    .reveal.is-visible { opacity: 1; transform: translateY(0); }
  </style>
</head>

<body>

  <!-- ═══ 01 · HEADER ═══ -->

  <!-- ═══ 02 · HERO ═══ -->

  <!-- ═══ 03 · STATS STRIP ═══ -->

  <!-- ═══ 04 · TRÊS PILARES ═══ -->

  <!-- ═══ 05 · ANÁLISE DE DOCUMENTOS ═══ -->

  <!-- ═══ 06 · CALCULADORA JUDICIAL ═══ -->

  <!-- ═══ 07 · PROCESSOS + DATAJUD + PRAZOS ═══ -->

  <!-- ═══ 08 · MANIFESTO ═══ -->

  <!-- ═══ 09 · FINANCEIRO + GERAÇÃO ═══ -->

  <!-- ═══ 10 · INTEGRAÇÕES ═══ -->

  <!-- ═══ 11 · TRUST / LGPD ═══ -->

  <!-- ═══ 12 · CTA + FOOTER ═══ -->

  <script>
    // JS goes here in later tasks
  </script>

</body>
</html>
```

- [ ] **Step 4: Run dev server and verify**

```bash
python manage.py runserver
```

Open `http://localhost:8000/`. Expected: blank cream-light page with no console errors. Fonts load (verify in DevTools Network tab).

- [ ] **Step 5: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): scaffold new home.html with base styles and fonts"
```

---

## Task 2: Section 01 · Glass Nav

**Files:**
- Modify: `templates/home.html` (replace `<!-- ═══ 01 · HEADER ═══ -->` comment)

- [ ] **Step 1: Add nav styles to `<style>` block**

Append inside `<style>`:

```css
.nav {
  position: sticky; top: 0; z-index: 50;
  background: rgba(255,255,255,.94);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(15,23,42,.08);
  transition: background 200ms, box-shadow 200ms;
}
.nav.is-scrolled { background: rgba(255,255,255,.98); box-shadow: 0 1px 12px rgba(15,23,42,.06); }
.nav-inner { max-width: 1200px; margin: 0 auto; padding: 0 2rem; height: 72px; display: flex; align-items: center; justify-content: space-between; }
.nav-logo { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.15rem; letter-spacing: -.015em; color: var(--ink); text-decoration: none; }
.nav-logo em { font-style: italic; color: var(--gold); }
.nav-links { display: flex; align-items: center; gap: 2.25rem; }
.nav-link { font-size: .82rem; color: var(--text-muted); text-decoration: none; position: relative; padding-bottom: 2px; }
.nav-link::after { content: ''; position: absolute; left: 0; bottom: 0; width: 0; height: 1px; background: var(--ink); transition: width 200ms ease-out; }
.nav-link:hover { color: var(--ink); }
.nav-link:hover::after { width: 100%; }
.nav-cta-row { display: flex; align-items: center; gap: .65rem; }
.nav-btn-out { font-size: .82rem; padding: .55rem 1.1rem; border-radius: 7px; color: var(--ink); border: 1px solid rgba(15,23,42,.18); text-decoration: none; transition: background 180ms; }
.nav-btn-out:hover { background: rgba(15,23,42,.04); }
.nav-btn-dark { font-size: .82rem; padding: .55rem 1.1rem; border-radius: 7px; background: var(--ink); color: var(--cream); text-decoration: none; font-weight: 600; display: inline-flex; align-items: center; gap: .4rem; transition: background 180ms, transform 140ms; }
.nav-btn-dark:hover { background: var(--ink-2); transform: translateY(-1px); }

.nav-mobile-toggle { display: none; background: none; border: 0; color: var(--ink); cursor: pointer; padding: .5rem; }
.nav-mobile-menu { display: none; padding: 1.5rem 2rem; gap: 1rem; background: #fff; border-bottom: 1px solid rgba(15,23,42,.08); flex-direction: column; }
.nav-mobile-menu a { font-family: 'Fraunces', serif; font-style: italic; font-size: 1.15rem; color: var(--ink); text-decoration: none; }
.nav-mobile-menu.is-open { display: flex; }

@media (max-width: 768px) {
  .nav-links, .nav-cta-row { display: none; }
  .nav-mobile-toggle { display: block; }
}
```

- [ ] **Step 2: Add nav HTML**

Replace `<!-- ═══ 01 · HEADER ═══ -->` block with:

```html
<!-- ═══ 01 · HEADER ═══ -->
<header class="nav" id="nav">
  <div class="nav-inner">
    <a href="{% url 'home' %}" class="nav-logo">Juri<em>AI</em></a>
    <nav class="nav-links">
      <a href="#funcionalidades" class="nav-link">Funcionalidades</a>
      <a href="#seguranca" class="nav-link">Segurança</a>
      <a href="{% url 'login' %}" class="nav-link">Entrar</a>
    </nav>
    <div class="nav-cta-row">
      <a href="{% url 'cadastro' %}" class="nav-btn-dark">Começar grátis
        <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </a>
    </div>
    <button class="nav-mobile-toggle" id="navToggle" aria-label="Abrir menu">
      <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
  </div>
  <div class="nav-mobile-menu" id="navMobileMenu">
    <a href="#funcionalidades">Funcionalidades</a>
    <a href="#seguranca">Segurança</a>
    <a href="{% url 'login' %}">Entrar</a>
    <a href="{% url 'cadastro' %}" style="color: var(--gold); font-style: normal; font-family: Inter, sans-serif; font-weight: 600; font-size: 1rem;">Começar grátis →</a>
  </div>
</header>
```

- [ ] **Step 3: Add mobile toggle JS to bottom `<script>`**

```javascript
const navToggle = document.getElementById('navToggle');
const navMobileMenu = document.getElementById('navMobileMenu');
navToggle?.addEventListener('click', () => navMobileMenu.classList.toggle('is-open'));
```

- [ ] **Step 4: Verify in browser**

Reload `http://localhost:8000/`. Expected: sticky white glass nav at top, logo with gold "AI", 3 links, dark CTA button. Resize to ≤768px → links/CTA hide, hamburger appears; click toggles a vertical menu.

- [ ] **Step 5: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 01 glass nav with mobile menu"
```

---

## Task 3: Section 02 · Hero (dark anchor 1)

**Files:**
- Modify: `templates/home.html` (replace section 02 placeholder)

- [ ] **Step 1: Add hero styles**

Append inside `<style>`:

```css
.hero {
  position: relative; overflow: hidden;
  min-height: 720px; padding: 8rem 2rem 5rem;
  background:
    linear-gradient(180deg, transparent 0%, rgba(15,23,42,.55) 60%, rgba(15,23,42,.95) 100%),
    linear-gradient(90deg, rgba(15,23,42,.65) 0%, rgba(15,23,42,.25) 50%, rgba(15,23,42,.7) 100%),
    url("{% static 'landing/law.png' %}") center 30% / cover,
    var(--ink);
  color: var(--cream);
}
.hero { animation: hero-breathe 14s ease-in-out infinite alternate; }
@keyframes hero-breathe { from { background-size: 100%, 100%, 100% 100%; } to { background-size: 100%, 100%, 103% 103%; } }
@media (prefers-reduced-motion: reduce) { .hero { animation: none; } }
.hero-orb { position: absolute; top: 20%; left: 50%; transform: translateX(-50%); width: 700px; height: 480px; background: radial-gradient(ellipse, rgba(212,165,71,.10) 0%, transparent 65%); filter: blur(48px); pointer-events: none; }
.hero-inner { position: relative; z-index: 2; max-width: 940px; margin: 0 auto; text-align: center; }

.badge { display: inline-flex; align-items: center; gap: .45rem; padding: .35rem .85rem; border-radius: 20px; background: rgba(212,165,71,.12); border: 1px solid rgba(212,165,71,.3); font-size: .68rem; letter-spacing: .16em; text-transform: uppercase; font-weight: 600; color: var(--gold); margin-bottom: 1.75rem; }
.badge .dot { width: 5px; height: 5px; border-radius: 50%; background: var(--gold); animation: dot-pulse 2.5s ease-in-out infinite; }
@keyframes dot-pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }

.hero h1 { font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2.8rem, 6vw, 5rem); line-height: 1.04; letter-spacing: -.022em; margin: 0 0 1.3rem; }
.hero h1 em { color: var(--gold); }
.hero .sub { font-size: clamp(1rem, 1.4vw, 1.1rem); opacity: .82; line-height: 1.65; max-width: 620px; margin: 0 auto 2.4rem; }

.btn-gold { padding: .9rem 1.75rem; background: var(--gold); color: var(--ink); border-radius: 8px; font-size: .92rem; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: .5rem; box-shadow: 0 0 30px rgba(212,165,71,.22); transition: background 180ms, transform 140ms, box-shadow 180ms; }
.btn-gold:hover { background: var(--gold-hover); transform: translateY(-1px); box-shadow: 0 0 40px rgba(212,165,71,.4); }
.btn-ghost-dark { padding: .9rem 1.75rem; background: transparent; color: var(--cream); border: 1px solid rgba(245,239,226,.25); border-radius: 8px; font-size: .92rem; font-weight: 500; text-decoration: none; display: inline-flex; align-items: center; gap: .5rem; transition: background 180ms, border-color 180ms; }
.btn-ghost-dark:hover { background: rgba(245,239,226,.05); border-color: rgba(245,239,226,.4); }

.hero .ctas { display: flex; gap: .8rem; justify-content: center; flex-wrap: wrap; margin-bottom: 2.8rem; }

.mockup-card-hero { max-width: 540px; margin: 0 auto; background: rgba(15,23,42,.58); backdrop-filter: blur(20px); border: 1px solid rgba(212,165,71,.2); border-radius: 11px; padding: 1.15rem 1.35rem; text-align: left; box-shadow: 0 24px 60px rgba(0,0,0,.45); }
.mc-head { display: flex; align-items: center; gap: .7rem; margin-bottom: .9rem; padding-bottom: .75rem; border-bottom: 1px solid rgba(245,239,226,.08); }
.mc-icon { width: 30px; height: 30px; border-radius: 6px; background: rgba(212,165,71,.15); border: 1px solid rgba(212,165,71,.3); display: flex; align-items: center; justify-content: center; font-family: 'Fraunces', serif; color: var(--gold); font-weight: 600; }
.mc-file { font-size: .82rem; font-weight: 600; }
.mc-file .meta { display: block; font-size: .65rem; opacity: .55; font-weight: 400; margin-top: 2px; }
.mc-risk { margin-left: auto; font-size: .6rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 700; color: var(--gold); }
.mc-item { display: flex; gap: .5rem; font-size: .78rem; line-height: 1.5; margin: .35rem 0; opacity: .88; }
.mc-item .pin { color: var(--gold); font-weight: 700; }
.mc-item strong { color: var(--cream); font-weight: 600; }

.hero-stats { margin-top: 2.6rem; display: flex; align-items: center; justify-content: center; gap: 2.5rem; flex-wrap: wrap; }
.hero-stats .stat { text-align: center; }
.hero-stats .stat .num { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.55rem; letter-spacing: -.015em; color: var(--cream); }
.hero-stats .stat .lbl { font-size: .65rem; letter-spacing: .14em; text-transform: uppercase; opacity: .55; margin-top: 3px; }
.hero-stats .sep { width: 1px; height: 28px; background: rgba(245,239,226,.15); }
```

- [ ] **Step 2: Add hero HTML**

Replace `<!-- ═══ 02 · HERO ═══ -->` block with:

```html
<!-- ═══ 02 · HERO ═══ -->
<section class="hero grain" id="hero">
  <div class="hero-orb"></div>
  <div class="hero-inner">

    <div class="badge"><span class="dot"></span>Plataforma de inteligência jurídica</div>

    <h1 class="serif">Jurídico inteligente,<br><em>resultados reais.</em></h1>

    <p class="sub">Documentos, processos, agenda e atendimento em um único ambiente. Inteligência avançada que apoia o julgamento do advogado sem jamais substituí-lo.</p>

    <div class="ctas">
      <a href="{% url 'cadastro' %}" class="btn-gold">Começar grátis
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </a>
      <a href="#funcionalidades" class="btn-ghost-dark">
        <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"/></svg>
        Ver demonstração
      </a>
    </div>

    <div class="mockup-card-hero">
      <div class="mc-head">
        <div class="mc-icon">§</div>
        <div class="mc-file">Petição inicial · Silva vs Construtora<span class="meta">Analisado há 14 segundos</span></div>
        <div class="mc-risk">Risco 28/100</div>
      </div>
      <div class="mc-item"><span class="pin">→</span><span><strong>3 inconsistências de prazo</strong> identificadas (fls. 4, 9 e 12)</span></div>
      <div class="mc-item"><span class="pin">→</span><span>Cláusula 4ª <strong>contradiz Art. 523 CPC</strong> sobre multa de 10%</span></div>
      <div class="mc-item"><span class="pin">→</span><span>Falta menção ao acórdão <strong>STJ Tema 1.061</strong> (precedente aplicável)</span></div>
    </div>

    <div class="hero-stats">
      <div class="stat"><div class="num">50+</div><div class="lbl">Tribunais</div></div>
      <div class="sep"></div>
      <div class="stat"><div class="num">DataJud</div><div class="lbl">Integrado</div></div>
      <div class="sep"></div>
      <div class="stat"><div class="num">24/7</div><div class="lbl">Atendimento</div></div>
    </div>

  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: dark hero with law.png photo dimmed by navy gradient + grain texture. Gold badge with pulsing dot. Large serif headline with "resultados reais" in gold italic. CTAs side by side. Mockup card centered below with realistic petition analysis content. Stats row at bottom.

Check at 375px width: hero is single-column, headline scales down, mockup card fills width.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 02 hero with law.png and risk mockup"
```

---

## Task 4: Section 03 · Stats Strip (light)

**Files:**
- Modify: `templates/home.html` (replace section 03 placeholder)

- [ ] **Step 1: Add styles**

Append inside `<style>`:

```css
.stats-strip { background: var(--cream); border-top: 1px solid #e3dcc8; border-bottom: 1px solid #e3dcc8; }
.stats-strip-inner { max-width: 1200px; margin: 0 auto; padding: 0 2rem; display: grid; grid-template-columns: repeat(3, 1fr); }
.stat-cell { padding: 1.75rem 1.5rem; display: flex; align-items: center; gap: 1rem; border-right: 1px solid #e3dcc8; }
.stat-cell:last-child { border-right: 0; }
.stat-icon { width: 44px; height: 44px; border-radius: 10px; background: rgba(212,165,71,.12); border: 1px solid rgba(212,165,71,.3); display: flex; align-items: center; justify-content: center; color: var(--gold); flex-shrink: 0; }
.stat-title { font-size: .92rem; font-weight: 600; letter-spacing: -.012em; color: var(--text-light); }
.stat-meta { font-size: .76rem; color: var(--text-muted); margin-top: 3px; font-weight: 400; }

@media (max-width: 768px) {
  .stats-strip-inner { grid-template-columns: 1fr; }
  .stat-cell { border-right: 0; border-bottom: 1px solid #e3dcc8; }
  .stat-cell:last-child { border-bottom: 0; }
}
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 03 · STATS STRIP ═══ -->` block with:

```html
<!-- ═══ 03 · STATS STRIP ═══ -->
<section class="stats-strip">
  <div class="stats-strip-inner">
    <div class="stat-cell">
      <div class="stat-icon">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z"/></svg>
      </div>
      <div>
        <div class="stat-title">3 agentes jurídicos especializados</div>
        <div class="stat-meta">JuriAI · SecretariaAI · JurisprudênciaAI</div>
      </div>
    </div>
    <div class="stat-cell">
      <div class="stat-icon">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
      </div>
      <div>
        <div class="stat-title">Análise jurisprudencial em segundos</div>
        <div class="stat-meta">Índice de risco e red flags automáticos</div>
      </div>
    </div>
    <div class="stat-cell">
      <div class="stat-icon">
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3"/></svg>
      </div>
      <div>
        <div class="stat-title">Atendimento autônomo 24/7</div>
        <div class="stat-meta">WhatsApp e Google Calendar integrados</div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: cream strip immediately under the hero, 3 columns separated by vertical hairlines, each with a gold icon + bold title + muted subtitle. At <768px stacks vertically with horizontal dividers.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 03 stats strip"
```

---

## Task 5: Section 04 · Três Pilares (light)

**Files:**
- Modify: `templates/home.html` (replace section 04 placeholder)

- [ ] **Step 1: Add styles**

```css
.section { padding: 7rem 2rem; }
.section-inner { max-width: 1200px; margin: 0 auto; }
.pretitle { font-family: 'Inter', sans-serif; font-size: .72rem; letter-spacing: .18em; text-transform: uppercase; font-weight: 600; color: var(--gold); margin-bottom: 1rem; }
.gold-rule { display: inline-block; width: 36px; height: 1px; background: var(--gold); margin-bottom: 1.1rem; }
.section h2 { font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2rem, 3.6vw, 2.9rem); line-height: 1.08; letter-spacing: -.018em; margin: 0 0 1rem; color: var(--text-light); }
.section h2 em { font-style: italic; color: var(--navy-700); }
.section .sub { font-size: 1rem; color: var(--text-muted); line-height: 1.65; max-width: 580px; }

.pillars-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-top: 3.5rem; }
.pillar-card { background: #fff; border: 1px solid #e3dcc8; border-radius: 14px; padding: 2rem 1.75rem; transition: border-color 220ms, box-shadow 220ms, transform 220ms; }
.pillar-card:hover { border-color: rgba(212,165,71,.4); box-shadow: 0 14px 40px rgba(15,23,42,.06); transform: translateY(-3px); }
.pillar-icon { width: 48px; height: 48px; border-radius: 10px; background: rgba(212,165,71,.12); border: 1px solid rgba(212,165,71,.3); display: flex; align-items: center; justify-content: center; color: var(--gold); margin-bottom: 1.5rem; }
.pillar-card h3 { font-family: 'Fraunces', serif; font-weight: 500; font-style: italic; font-size: 1.35rem; letter-spacing: -.012em; color: var(--text-light); margin: 0 0 .55rem; }
.pillar-card p { font-size: .92rem; color: var(--text-muted); line-height: 1.6; margin: 0; }

@media (max-width: 900px) {
  .pillars-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 04 · TRÊS PILARES ═══ -->` block with:

```html
<!-- ═══ 04 · TRÊS PILARES ═══ -->
<section class="section reveal" id="funcionalidades">
  <div class="section-inner">
    <span class="pretitle">Capacidades</span>
    <div><span class="gold-rule"></span></div>
    <h2>Três pilares, <em>um ambiente.</em></h2>
    <p class="sub">Cada agente é especializado num eixo do trabalho jurídico, sem misturar contextos nem dados.</p>

    <div class="pillars-grid">
      <div class="pillar-card">
        <div class="pillar-icon">
          <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/></svg>
        </div>
        <h3>Análise de Documentos.</h3>
        <p>Identifica riscos, inconsistências e red flags antes do protocolo.</p>
      </div>
      <div class="pillar-card">
        <div class="pillar-icon">
          <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"/></svg>
        </div>
        <h3>Chat por Cliente.</h3>
        <p>Cada cliente tem seu próprio assistente treinado com os documentos do caso.</p>
      </div>
      <div class="pillar-card">
        <div class="pillar-icon">
          <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3"/></svg>
        </div>
        <h3>Secretaria Autônoma.</h3>
        <p>Atende, agenda e mantém a comunicação fluindo sem intervenção humana.</p>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: white section under stats strip, gold pretitle "Capacidades", thin gold rule, serif headline with italic navy "um ambiente", 3 cards in a row with gold icon, italic serif title (followed by period), short description. Hover lifts the card slightly. Stacks to single column at <900px.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 04 three pillars"
```

---

## Task 6: Section 05 · Análise de Documentos (light, text-left/mockup-right)

**Files:**
- Modify: `templates/home.html` (replace section 05 placeholder)

- [ ] **Step 1: Add shared module styles (used by 05, 06, 07, 09)**

```css
.module { padding: 6rem 2rem; }
.module.alt { background: var(--cream); }
.module-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; }
.module-inner.reverse { direction: rtl; }
.module-inner.reverse > * { direction: ltr; }
.module-text .pretitle { color: var(--gold); }
.module-text h2 { font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(1.9rem, 3.2vw, 2.6rem); line-height: 1.1; letter-spacing: -.018em; margin: 0 0 1.1rem; color: var(--text-light); }
.module-text h2 em { font-style: italic; color: var(--navy-700); }
.module-text p { font-size: 1rem; color: var(--text-muted); line-height: 1.7; margin: 0 0 1.2rem; }
.module-bullets { list-style: none; padding: 0; margin: 1.4rem 0 0; }
.module-bullets li { display: flex; gap: .65rem; font-size: .92rem; color: var(--text-light); padding: .4rem 0; line-height: 1.55; }
.module-bullets li::before { content: '→'; color: var(--gold); font-weight: 700; flex-shrink: 0; }
.module-chips { margin-top: 1.6rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.chip-light { font-size: .72rem; padding: .28rem .65rem; border-radius: 5px; background: rgba(15,23,42,.05); color: var(--text-light); border: 1px solid rgba(15,23,42,.1); font-weight: 500; }

.module-mockup { background: #fff; border: 1px solid #e3dcc8; border-radius: 14px; padding: 1.5rem; box-shadow: 0 18px 50px rgba(15,23,42,.08); }
.module-mockup .mockup-title { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; font-weight: 600; color: var(--text-muted); padding-bottom: .8rem; border-bottom: 1px solid #e3dcc8; margin-bottom: 1rem; }

@media (max-width: 1024px) {
  .module-inner { grid-template-columns: 1fr; gap: 2.5rem; }
  .module-inner.reverse { direction: ltr; }
}
```

- [ ] **Step 2: Add section 05 specific mockup style**

```css
.mockup-risk { padding: 1rem; }
.mockup-risk .risk-big { display: flex; align-items: baseline; gap: .5rem; margin-bottom: .8rem; }
.mockup-risk .risk-big .num { font-family: 'Fraunces', serif; font-size: 3rem; font-weight: 500; color: var(--gold); letter-spacing: -.02em; line-height: 1; }
.mockup-risk .risk-big .lbl { font-size: .82rem; color: var(--text-muted); }
.mockup-risk .flag { padding: .65rem .85rem; background: var(--cream); border-left: 2px solid var(--gold); border-radius: 4px; margin-bottom: .5rem; }
.mockup-risk .flag .cat { font-size: .65rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 700; color: var(--gold); margin-bottom: .2rem; }
.mockup-risk .flag .desc { font-size: .82rem; color: var(--text-light); line-height: 1.45; }
```

- [ ] **Step 3: Add HTML**

Replace `<!-- ═══ 05 · ANÁLISE DE DOCUMENTOS ═══ -->` block with:

```html
<!-- ═══ 05 · ANÁLISE DE DOCUMENTOS ═══ -->
<section class="module reveal">
  <div class="module-inner">
    <div class="module-text">
      <span class="pretitle">Módulo 01</span>
      <div><span class="gold-rule"></span></div>
      <h2>Risco identificado <em>antes do protocolo.</em></h2>
      <p>Carregue petições, contratos e pareceres. O JuriAI extrai o texto via OCR, percorre cada cláusula e devolve um índice de risco com red flags categorizados.</p>
      <ul class="module-bullets">
        <li>OCR automático em PDF, DOCX e imagens</li>
        <li>Índice de risco de 0 a 100 com explicação por categoria</li>
        <li>Red flags por tema: prazo, jurisprudência, formatação, coerência interna</li>
        <li>Citações aos artigos do CPC e acórdãos aplicáveis</li>
      </ul>
      <div class="module-chips">
        <span class="chip-light">PDF</span>
        <span class="chip-light">DOCX</span>
        <span class="chip-light">OCR</span>
        <span class="chip-light">Petições</span>
        <span class="chip-light">Contratos</span>
        <span class="chip-light">Pareceres</span>
      </div>
    </div>
    <div class="module-mockup">
      <div class="mockup-title">Análise · Silva vs Construtora</div>
      <div class="mockup-risk">
        <div class="risk-big"><span class="num">28</span><span class="lbl">/ 100 · Risco baixo</span></div>
        <div class="flag">
          <div class="cat">Prazo</div>
          <div class="desc">3 inconsistências de prazo identificadas (fls. 4, 9 e 12).</div>
        </div>
        <div class="flag">
          <div class="cat">Jurisprudência</div>
          <div class="desc">Cláusula 4ª contradiz Art. 523 CPC sobre multa de 10%.</div>
        </div>
        <div class="flag">
          <div class="cat">Precedente</div>
          <div class="desc">Falta menção ao acórdão STJ Tema 1.061 (precedente aplicável).</div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 4: Verify in browser**

Reload. Expected: light section, 2 columns at ≥1024px (text left, mockup right). Text side: gold pretitle "Módulo 01", gold rule, headline "Risco identificado *antes do protocolo*", paragraph, bulleted list with gold arrows, chips. Mockup side: card with title strip, big gold "28" + "/100 · Risco baixo", 3 flag cards with cream background and gold left border. At <1024px stacks vertically.

- [ ] **Step 5: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 05 document analysis with risk mockup"
```

---

## Task 7: Section 06 · Calculadora Judicial (light, mockup-left/text-right)

**Files:**
- Modify: `templates/home.html` (replace section 06 placeholder)

- [ ] **Step 1: Add calc mockup styles**

```css
.module.calc { background: var(--cream); }
.mockup-calc { padding: 0; }
.mockup-calc .calc-summary { padding: 1.2rem; background: var(--ink); color: var(--cream); border-radius: 10px 10px 0 0; margin: -1.5rem -1.5rem 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.mockup-calc .calc-summary .item .lbl { font-size: .6rem; letter-spacing: .14em; text-transform: uppercase; opacity: .55; }
.mockup-calc .calc-summary .item .val { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.1rem; margin-top: 3px; }
.mockup-calc .calc-summary .item.total .val { color: var(--gold); font-size: 1.35rem; }
.mockup-calc table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; font-size: .8rem; }
.mockup-calc th { text-align: left; font-size: .65rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-muted); font-weight: 600; padding: .55rem .4rem; border-bottom: 1px solid #e3dcc8; }
.mockup-calc th.r, .mockup-calc td.r { text-align: right; }
.mockup-calc td { padding: .55rem .4rem; border-bottom: 1px solid #f1efe9; }
.mockup-calc tr:last-child td { border-bottom: 0; font-weight: 600; }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 06 · CALCULADORA JUDICIAL ═══ -->` block with:

```html
<!-- ═══ 06 · CALCULADORA JUDICIAL ═══ -->
<section class="module calc reveal">
  <div class="module-inner reverse">
    <div class="module-text">
      <span class="pretitle">Módulo 02</span>
      <div><span class="gold-rule"></span></div>
      <h2>Cálculos prontos <em>para protocolo.</em></h2>
      <p>Atualização monetária mês a mês pelo índice oficial, juros conforme o regime do processo e exportação em PDF pronta para protocolo. Sem planilha à parte.</p>
      <ul class="module-bullets">
        <li>Índices: IPCA-E, INPC, SELIC, TR, IGP-M e Taxa Legal (Lei 14.905/2024)</li>
        <li>Juros simples ou compostos, com regime customizável por período</li>
        <li>Multa Art. 523 CPC e honorários sucumbenciais configuráveis</li>
        <li>Tabelas próprias dos TJs (SP, RJ, MG, PR, RS), CJF e TST</li>
        <li>Comparador de cenários lado a lado para negociação</li>
      </ul>
    </div>
    <div class="module-mockup mockup-calc">
      <div class="calc-summary">
        <div class="item"><div class="lbl">Corrigido</div><div class="val">R$ 38.420,16</div></div>
        <div class="item"><div class="lbl">Juros</div><div class="val">R$ 6.708,03</div></div>
        <div class="item"><div class="lbl">Multa</div><div class="val">R$ 4.512,82</div></div>
        <div class="item total"><div class="lbl">Total</div><div class="val">R$ 49.641,01</div></div>
      </div>
      <table>
        <thead><tr><th>Mês</th><th class="r">IPCA-E %</th><th class="r">Correção</th><th class="r">Juros</th><th class="r">Subtotal</th></tr></thead>
        <tbody>
          <tr><td>jan/26</td><td class="r">0,47</td><td class="r">141,12</td><td class="r">300,42</td><td class="r">30.441,54</td></tr>
          <tr><td>fev/26</td><td class="r">0,33</td><td class="r">100,57</td><td class="r">301,04</td><td class="r">30.843,15</td></tr>
          <tr><td>mar/26</td><td class="r">0,55</td><td class="r">169,77</td><td class="r">302,06</td><td class="r">31.314,98</td></tr>
          <tr><td>abr/26</td><td class="r">0,29</td><td class="r">90,93</td><td class="r">302,99</td><td class="r">31.708,90</td></tr>
          <tr><td>… 18 meses</td><td class="r">…</td><td class="r">…</td><td class="r">…</td><td class="r">…</td></tr>
          <tr><td>Total</td><td class="r">-</td><td class="r"><strong>R$ 8.420,16</strong></td><td class="r"><strong>R$ 6.708,03</strong></td><td class="r"><strong>R$ 45.128,19</strong></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: cream-background section. At ≥1024px, mockup is on the left, text on the right (uses `.reverse`). Mockup shows dark navy summary strip with 4 columns ending in gold "Total", then a clean table with monthly evolution. Stacks vertically <1024px.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 06 judicial calculator with table mockup"
```

---

## Task 8: Section 07 · Processos + DataJud + Prazos (light, text-left/mockup-right)

**Files:**
- Modify: `templates/home.html` (replace section 07 placeholder)

- [ ] **Step 1: Add timeline mockup styles**

```css
.mockup-timeline { padding: 1.5rem; }
.mockup-timeline .tl-item { display: flex; gap: 1rem; padding: .65rem 0; position: relative; }
.mockup-timeline .tl-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; position: relative; }
.mockup-timeline .tl-dot.datajud { background: var(--navy-700); }
.mockup-timeline .tl-dot.manual { background: #cbd5e1; }
.mockup-timeline .tl-dot::after { content: ''; position: absolute; top: 14px; left: 4px; width: 2px; height: 30px; background: #e3dcc8; }
.mockup-timeline .tl-item:last-child .tl-dot::after { display: none; }
.mockup-timeline .tl-content { flex: 1; }
.mockup-timeline .tl-date { font-size: .68rem; color: var(--text-muted); letter-spacing: .08em; text-transform: uppercase; font-weight: 600; }
.mockup-timeline .tl-desc { font-size: .88rem; color: var(--text-light); line-height: 1.5; margin-top: 2px; }
.mockup-timeline .tl-src { display: inline-block; font-size: .6rem; padding: .15rem .45rem; border-radius: 3px; margin-left: .4rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; vertical-align: middle; }
.mockup-timeline .tl-src.datajud { background: rgba(30,58,95,.1); color: var(--navy-700); }
.mockup-timeline .tl-src.manual { background: rgba(100,116,139,.1); color: var(--text-muted); }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 07 · PROCESSOS + DATAJUD + PRAZOS ═══ -->` block with:

```html
<!-- ═══ 07 · PROCESSOS + DATAJUD + PRAZOS ═══ -->
<section class="module reveal">
  <div class="module-inner">
    <div class="module-text">
      <span class="pretitle">Módulo 03</span>
      <div><span class="gold-rule"></span></div>
      <h2>Cada processo <em>sempre atualizado.</em></h2>
      <p>Vincule o número CNJ e o JuriAI consulta o DataJud todo dia. Andamentos chegam automáticos, prazos viram alerta de e-mail e evento no Google Calendar.</p>
      <ul class="module-bullets">
        <li>Integração nativa com DataJud (CNJ) e atualização diária automática</li>
        <li>Timeline visual de andamentos com origem (DataJud ou manual)</li>
        <li>Prazos com alerta por e-mail nos dias configurados antes do vencimento</li>
        <li>Sincronização bidirecional com Google Calendar</li>
        <li>Cobertura de todos os tribunais brasileiros suportados pelo DataJud</li>
      </ul>
    </div>
    <div class="module-mockup mockup-timeline">
      <div class="mockup-title">0042586-12.2025.8.26.0100 · Silva vs Construtora</div>
      <div class="tl-item">
        <div class="tl-dot datajud"></div>
        <div class="tl-content">
          <div class="tl-date">14/05/2026<span class="tl-src datajud">DataJud</span></div>
          <div class="tl-desc">Decisão interlocutória publicada. Concedida tutela provisória parcial.</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-dot datajud"></div>
        <div class="tl-content">
          <div class="tl-date">02/05/2026<span class="tl-src datajud">DataJud</span></div>
          <div class="tl-desc">Audiência de conciliação designada para 18/06/2026 às 14h.</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-dot manual"></div>
        <div class="tl-content">
          <div class="tl-date">28/04/2026<span class="tl-src manual">Manual</span></div>
          <div class="tl-desc">Contrato original anexado ao processo (revisado pelo escritório).</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-dot datajud"></div>
        <div class="tl-content">
          <div class="tl-date">15/04/2026<span class="tl-src datajud">DataJud</span></div>
          <div class="tl-desc">Distribuição inicial. 4ª Vara Cível de São Paulo.</div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: white section with module on text-left/mockup-right layout. Mockup shows process number as title, then vertical timeline with navy dots (DataJud) and gray dots (Manual), each with date + source badge + description, connected by thin vertical line.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 07 processes with DataJud timeline"
```

---

## Task 9: Section 08 · Manifesto with books.jpg (dark anchor 2)

**Files:**
- Modify: `templates/home.html` (replace section 08 placeholder)

- [ ] **Step 1: Add styles**

```css
.manifesto {
  position: relative; overflow: hidden;
  padding: 9rem 2rem;
  background:
    linear-gradient(90deg, rgba(10,10,10,.92) 0%, rgba(10,10,10,.5) 50%, rgba(10,10,10,.92) 100%),
    url("{% static 'landing/books.jpg' %}") center / cover,
    #0a0a0a;
  color: var(--cream);
  text-align: center;
}
.manifesto-inner { position: relative; z-index: 2; max-width: 640px; margin: 0 auto; }
.manifesto .pretitle { color: var(--gold); }
.manifesto h2 { font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2.2rem, 4.2vw, 3.4rem); line-height: 1.08; letter-spacing: -.02em; margin: 1rem 0; color: var(--cream); }
.manifesto h2 em { font-style: italic; color: var(--gold); }
.manifesto p { font-size: 1.05rem; line-height: 1.7; opacity: .8; margin: 1.4rem 0 0; }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 08 · MANIFESTO ═══ -->` block with:

```html
<!-- ═══ 08 · MANIFESTO ═══ -->
<section class="manifesto grain reveal">
  <div class="manifesto-inner">
    <span class="pretitle">Manifesto</span>
    <div><span class="gold-rule"></span></div>
    <h2>Tradição que pensa, <em>inteligência que age.</em></h2>
    <p>Cada decisão jurídica nasce sobre séculos de doutrina. O JuriAI torna esse acervo, e o seu próprio, instantaneamente acessível. O julgamento continua seu.</p>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: full-width dark section between section 07 and section 09. books.jpg background heavily darkened by lateral gradient (dark on sides, slightly less in center). Grain overlay visible at close inspection. Centered text: gold pretitle "Manifesto", gold rule, large serif headline with italic gold "inteligência que age", body paragraph below.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 08 manifesto with books background"
```

---

## Task 10: Section 09 · Financeiro + Geração de Documentos (light, 2 columns)

**Files:**
- Modify: `templates/home.html` (replace section 09 placeholder)

- [ ] **Step 1: Add styles**

```css
.duo { padding: 7rem 2rem; }
.duo-inner { max-width: 1200px; margin: 0 auto; }
.duo-head { max-width: 580px; margin-bottom: 3.5rem; }
.duo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
.duo-col { background: #fff; border: 1px solid #e3dcc8; border-radius: 14px; padding: 2.25rem; }
.duo-col h3 { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.65rem; line-height: 1.12; margin: 0 0 .8rem; }
.duo-col h3 em { font-style: italic; color: var(--navy-700); }
.duo-col p { font-size: .92rem; color: var(--text-muted); line-height: 1.65; margin: 0 0 1rem; }
.duo-col ul { list-style: none; padding: 0; margin: 0 0 1.5rem; }
.duo-col ul li { display: flex; gap: .55rem; font-size: .88rem; padding: .25rem 0; color: var(--text-light); }
.duo-col ul li::before { content: '·'; color: var(--gold); font-weight: 700; font-size: 1.2rem; line-height: 1; flex-shrink: 0; }

.mini-mock { background: var(--cream); border: 1px solid #e3dcc8; border-radius: 10px; padding: 1rem; }
.mini-mock .kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; }
.mini-mock .kpi .lbl { font-size: .6rem; letter-spacing: .12em; text-transform: uppercase; color: var(--text-muted); font-weight: 600; }
.mini-mock .kpi .val { font-family: 'Fraunces', serif; font-size: 1.1rem; font-weight: 500; margin-top: 4px; }
.mini-mock .kpi.warn .val { color: #b8860b; }

.editor-mock { background: var(--ink); color: var(--cream); border-radius: 10px; overflow: hidden; }
.editor-mock .em-head { padding: .5rem .9rem; background: rgba(255,255,255,.05); font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); border-bottom: 1px solid rgba(255,255,255,.05); display: flex; gap: .5rem; }
.editor-mock .em-tab.active { color: var(--cream); }
.editor-mock .em-body { padding: 1rem; font-size: .8rem; line-height: 1.6; font-family: 'Fraunces', serif; opacity: .9; }
.editor-mock .em-body strong { color: var(--gold); font-weight: 500; }

@media (max-width: 900px) {
  .duo-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 09 · FINANCEIRO + GERAÇÃO ═══ -->` block with:

```html
<!-- ═══ 09 · FINANCEIRO + GERAÇÃO ═══ -->
<section class="duo reveal">
  <div class="duo-inner">
    <div class="duo-head">
      <span class="pretitle">Módulos 04 e 05</span>
      <div><span class="gold-rule"></span></div>
      <h2 style="font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2rem, 3.6vw, 2.9rem); line-height: 1.08; letter-spacing: -.018em;">Operação financeira e <em style="font-style: italic; color: var(--navy-700);">redação jurídica.</em></h2>
      <p class="sub">Dois módulos que fecham o ciclo: gerir receita do escritório e produzir as peças escritas que sustentam cada processo.</p>
    </div>
    <div class="duo-grid">
      <div class="duo-col">
        <h3>Receita visível, <em>inadimplência controlada.</em></h3>
        <p>Honorários por tipo (fixo, êxito, hora, mensalidade), pagamentos parciais, alertas de vencimento e fluxo de caixa exportável.</p>
        <ul>
          <li>Painel com receita do mês, a receber e em atraso</li>
          <li>Alerta de inadimplência via WhatsApp para o advogado</li>
          <li>Exportação em PDF e Excel para contabilidade</li>
        </ul>
        <div class="mini-mock">
          <div class="kpis">
            <div class="kpi"><div class="lbl">Recebido</div><div class="val">R$ 24.800</div></div>
            <div class="kpi"><div class="lbl">A receber</div><div class="val">R$ 18.200</div></div>
            <div class="kpi warn"><div class="lbl">Em atraso</div><div class="val">R$ 4.350</div></div>
          </div>
        </div>
      </div>
      <div class="duo-col">
        <h3>Petições e contratos <em>em minutos.</em></h3>
        <p>Templates editáveis em markdown, variáveis automáticas do cliente e do processo, agente especializado em redação jurídica brasileira.</p>
        <ul>
          <li>5 templates pré-prontos: honorários, procuração, notificação, petição inicial, acordo</li>
          <li>Variáveis: nome do cliente, número CNJ, data, valor da causa</li>
          <li>Exportação direta em .docx e .pdf prontos para protocolo</li>
        </ul>
        <div class="mini-mock editor-mock">
          <div class="em-head">
            <span class="em-tab active">Editor</span>
            <span class="em-tab">Preview</span>
            <span class="em-tab">Exportar</span>
          </div>
          <div class="em-body">
            Excelentíssimo Senhor Doutor Juiz da <strong>4ª Vara Cível</strong> da Comarca de São Paulo,<br><br>
            <strong>{{cliente.nome}}</strong>, qualificado nos autos, vem respeitosamente perante Vossa Excelência…
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: white section. Header with pretitle + serif headline + sub. Below, 2 equal cards. Card 1: financial topic with KPI mockup (cream background, 3 columns, gold/black "Em atraso" warning color). Card 2: doc generation with dark "editor" mockup showing tabs and a fake petition template snippet. Stacks at <900px.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 09 financial and document generation"
```

---

## Task 11: Section 10 · Integrações (light, slim strip)

**Files:**
- Modify: `templates/home.html` (replace section 10 placeholder)

- [ ] **Step 1: Add styles**

```css
.integrations { padding: 3.5rem 2rem; background: var(--cream); border-top: 1px solid #e3dcc8; border-bottom: 1px solid #e3dcc8; }
.integrations-inner { max-width: 1200px; margin: 0 auto; text-align: center; }
.integrations .pretitle { color: var(--text-muted); }
.integrations-logos { display: flex; align-items: center; justify-content: center; gap: 3rem; flex-wrap: wrap; margin-top: 1.5rem; }
.integration-logo { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.2rem; color: var(--text-muted); letter-spacing: -.01em; transition: color 200ms; cursor: default; opacity: .7; }
.integration-logo:hover { color: var(--text-light); opacity: 1; }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 10 · INTEGRAÇÕES ═══ -->` block with:

```html
<!-- ═══ 10 · INTEGRAÇÕES ═══ -->
<section class="integrations reveal">
  <div class="integrations-inner">
    <span class="pretitle">Integrado com o que você já usa</span>
    <div class="integrations-logos">
      <span class="integration-logo">DataJud · CNJ</span>
      <span class="integration-logo">Google Calendar</span>
      <span class="integration-logo">WhatsApp</span>
      <span class="integration-logo">Stripe</span>
      <span class="integration-logo">Modelos avançados</span>
    </div>
  </div>
</section>
```

Note: "Modelos avançados" is a neutral label per spec section 13 open question (avoids exposing the OpenAI brand). If real logos become available later, replace each `<span>` with an `<img>` tag.

- [ ] **Step 3: Verify in browser**

Reload. Expected: thin cream strip between section 09 and 11. Centered "Integrado com o que você já usa" label, then a row of 5 serif-styled text labels acting as logos. Stack to wrap on narrow screens.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 10 integrations strip"
```

---

## Task 12: Section 11 · Trust / Segurança / LGPD (light, 4-card grid)

**Files:**
- Modify: `templates/home.html` (replace section 11 placeholder)

- [ ] **Step 1: Add styles**

```css
.trust { padding: 7rem 2rem; }
.trust-inner { max-width: 1200px; margin: 0 auto; }
.trust-head { max-width: 620px; margin-bottom: 3.5rem; }
.trust-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.25rem; }
.trust-card { background: #fff; border: 1px solid #e3dcc8; border-radius: 12px; padding: 1.75rem; transition: border-color 220ms, box-shadow 220ms; }
.trust-card:hover { border-color: rgba(15,23,42,.25); box-shadow: 0 10px 30px rgba(15,23,42,.06); }
.trust-icon { width: 38px; height: 38px; border-radius: 9px; background: rgba(212,165,71,.12); border: 1px solid rgba(212,165,71,.3); display: flex; align-items: center; justify-content: center; color: var(--gold); margin-bottom: 1.1rem; }
.trust-card h3 { font-family: 'Inter', sans-serif; font-weight: 600; font-size: .98rem; letter-spacing: -.012em; color: var(--text-light); margin: 0 0 .4rem; }
.trust-card p { font-size: .85rem; color: var(--text-muted); line-height: 1.55; margin: 0; }

.trust-featured { background: var(--ink); color: var(--cream); border-radius: 12px; padding: 1.5rem 2rem; margin-top: 1.25rem; display: flex; align-items: center; gap: 1rem; }
.trust-featured .flag { font-family: 'Fraunces', serif; font-style: italic; font-size: 1.05rem; color: var(--gold); }
.trust-featured .body { font-size: .92rem; opacity: .85; }

@media (max-width: 900px) { .trust-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 500px) { .trust-grid { grid-template-columns: 1fr; } .trust-featured { flex-direction: column; text-align: center; } }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 11 · TRUST / LGPD ═══ -->` block with:

```html
<!-- ═══ 11 · TRUST / LGPD ═══ -->
<section class="trust reveal" id="seguranca">
  <div class="trust-inner">
    <div class="trust-head">
      <span class="pretitle">Confiança</span>
      <div><span class="gold-rule"></span></div>
      <h2 style="font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2rem, 3.6vw, 2.9rem); line-height: 1.08; letter-spacing: -.018em;">Seus dados, <em style="font-style: italic; color: var(--navy-700);">seu controle.</em></h2>
      <p class="sub">Construído desde o primeiro dia para advogados que levam dados de clientes a sério.</p>
    </div>
    <div class="trust-grid">
      <div class="trust-card">
        <div class="trust-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/></svg>
        </div>
        <h3>Dados criptografados</h3>
        <p>Em trânsito e em repouso, com chave gerenciada pelo escritório.</p>
      </div>
      <div class="trust-card">
        <div class="trust-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z"/></svg>
        </div>
        <h3>LGPD nativo</h3>
        <p>Consentimento auditado, exclusão de conta completa, exportação de dados.</p>
      </div>
      <div class="trust-card">
        <div class="trust-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z"/></svg>
        </div>
        <h3>Auditoria completa</h3>
        <p>Cada alteração em cliente, processo ou documento fica registrada e visível.</p>
      </div>
      <div class="trust-card">
        <div class="trust-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6"><path stroke-linecap="round" stroke-linejoin="round" d="M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5zm6-10.125a1.875 1.875 0 11-3.75 0 1.875 1.875 0 013.75 0zm1.294 6.336a6.721 6.721 0 01-3.17.789 6.721 6.721 0 01-3.168-.789 3.376 3.376 0 016.338 0z"/></svg>
        </div>
        <h3>Isolamento por cliente</h3>
        <p>Cada cliente tem seu próprio espaço de busca. Nada vaza entre casos.</p>
      </div>
    </div>
    <div class="trust-featured">
      <span class="flag">100% Brasil.</span>
      <span class="body">Plataforma e infraestrutura no Brasil, suporte em português, conformidade com LGPD desde o primeiro commit.</span>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: white section under integrations. Header block. 4 white cards in a row with gold icons. Hover lifts. Below, a dark navy featured card with gold italic "100% Brasil." and a body line. Responsive: 4 → 2 → 1 columns.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 11 trust and LGPD"
```

---

## Task 13: Section 12 · CTA + Footer (dark anchor 3)

**Files:**
- Modify: `templates/home.html` (replace section 12 placeholder)

- [ ] **Step 1: Add styles**

```css
.cta-final {
  position: relative; overflow: hidden;
  padding: 7rem 2rem 5rem;
  background:
    radial-gradient(ellipse 70% 60% at 50% 50%, rgba(212,165,71,.12) 0%, transparent 65%),
    var(--ink);
  color: var(--cream); text-align: center;
}
.cta-final-inner { position: relative; z-index: 2; max-width: 640px; margin: 0 auto; }
.cta-final .badge { margin-bottom: 1.6rem; }
.cta-final h2 { font-family: 'Fraunces', serif; font-weight: 500; font-size: clamp(2.4rem, 4.5vw, 3.5rem); line-height: 1.08; letter-spacing: -.02em; margin: 0 0 .9rem; }
.cta-final h2 em { font-style: italic; color: var(--gold); }
.cta-final p { font-size: 1rem; opacity: .8; margin: 0 0 2.4rem; }
.cta-final .trust-line { margin-top: 2.4rem; padding-top: 2rem; border-top: 1px solid rgba(245,239,226,.1); display: flex; align-items: center; justify-content: center; gap: 1.5rem; flex-wrap: wrap; font-size: .78rem; opacity: .6; }
.cta-final .trust-line span { display: inline-flex; align-items: center; gap: .35rem; }
.cta-final .trust-line .sep { width: 1px; height: 14px; background: rgba(245,239,226,.2); }

.footer { background: var(--ink); color: rgba(245,239,226,.55); padding: 4rem 2rem 2rem; border-top: 1px solid rgba(245,239,226,.06); font-size: .85rem; }
.footer-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 2.5rem; margin-bottom: 3rem; }
.footer .col h4 { font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 700; color: var(--cream); margin: 0 0 1rem; }
.footer .col ul { list-style: none; padding: 0; margin: 0; }
.footer .col li { margin-bottom: .55rem; font-size: .82rem; }
.footer .col a { color: inherit; text-decoration: none; transition: color 180ms; }
.footer .col a:hover { color: var(--cream); }
.footer .brand .logo { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.25rem; color: var(--cream); }
.footer .brand .logo em { font-style: italic; color: var(--gold); }
.footer .brand .tag { font-size: .8rem; margin-top: .5rem; line-height: 1.5; max-width: 280px; }
.footer-bottom { max-width: 1200px; margin: 0 auto; padding-top: 1.5rem; border-top: 1px solid rgba(245,239,226,.06); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; font-size: .76rem; }

@media (max-width: 900px) { .footer-inner { grid-template-columns: 1fr 1fr; } }
@media (max-width: 500px) { .footer-inner { grid-template-columns: 1fr; } }
```

- [ ] **Step 2: Add HTML**

Replace `<!-- ═══ 12 · CTA + FOOTER ═══ -->` block with:

```html
<!-- ═══ 12 · CTA + FOOTER ═══ -->
<section class="cta-final grain">
  <div class="cta-final-inner">
    <div class="badge"><span class="dot"></span>Comece grátis</div>
    <h2>Pronto para trabalhar <em>diferente?</em></h2>
    <p>Crie sua conta. Sem cartão de crédito.</p>
    <a href="{% url 'cadastro' %}" class="btn-gold">Criar conta gratuita
      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
    </a>
    <div class="trust-line">
      <span>
        <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"/></svg>
        Dados criptografados
      </span>
      <span class="sep"></span>
      <span>Configuração em minutos</span>
      <span class="sep"></span>
      <span>Suporte em português</span>
    </div>
  </div>
</section>

<footer class="footer">
  <div class="footer-inner">
    <div class="col brand">
      <div class="logo">Juri<em>AI</em></div>
      <p class="tag">Plataforma de inteligência jurídica para escritórios brasileiros.</p>
    </div>
    <div class="col">
      <h4>Produto</h4>
      <ul>
        <li><a href="#funcionalidades">Funcionalidades</a></li>
        <li><a href="#seguranca">Segurança</a></li>
        <li><a href="{% url 'login' %}">Entrar</a></li>
        <li><a href="{% url 'cadastro' %}">Criar conta</a></li>
      </ul>
    </div>
    <div class="col">
      <h4>Legal</h4>
      <ul>
        <li><a href="/privacidade/">Privacidade</a></li>
        <li><a href="/termos/">Termos de uso</a></li>
      </ul>
    </div>
    <div class="col">
      <h4>Contato</h4>
      <ul>
        <li>contato@juriai.com.br</li>
        <li>São Paulo, Brasil</li>
      </ul>
    </div>
  </div>
  <div class="footer-bottom">
    <span>© 2026 JuriAI. Todos os direitos reservados.</span>
    <span>Feito no Brasil para o Direito brasileiro.</span>
  </div>
</footer>
```

- [ ] **Step 3: Verify in browser**

Reload. Expected: dark CTA section with gold radial glow at center, badge, big serif headline with italic gold "diferente?", sub line, prominent gold button. Trust line below with 3 items. Footer below with 4 columns (brand left, then product/legal/contact), bottom strip with copyright and tagline. Responsive grid collapses.

Verify URLs work: clicking "Entrar" should hit the login page, "Criar conta" the cadastro, "Privacidade" and "Termos" the existing pages.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): section 12 final CTA and footer"
```

---

## Task 14: Reveal on scroll JS

**Files:**
- Modify: `templates/home.html` (extend the bottom `<script>` block)

- [ ] **Step 1: Add IntersectionObserver script**

Inside the existing `<script>` tag at the bottom of body, add:

```javascript
// Reveal sections as they enter viewport (respects prefers-reduced-motion)
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const reveals = document.querySelectorAll('.reveal');

if (prefersReducedMotion) {
  reveals.forEach(el => el.classList.add('is-visible'));
} else {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });
  reveals.forEach(el => revealObserver.observe(el));
}
```

- [ ] **Step 2: Verify in browser**

Reload. Scroll from the top. Expected: hero is visible immediately; as each section below comes into view (~12% threshold), it fades in and slides up over 800ms. Already-visible sections never re-trigger.

If a section starts already visible at page load, it may flash; consider also adding `.is-visible` to the hero on load if it has `.reveal`. The hero in this build does not have `.reveal`, so this should be fine.

- [ ] **Step 3: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): reveal sections on scroll with IntersectionObserver"
```

---

## Task 15: Glass nav scroll state

**Files:**
- Modify: `templates/home.html` (extend the bottom `<script>` block)

- [ ] **Step 1: Add scroll listener**

Inside `<script>`, add:

```javascript
// Glass nav becomes more solid on scroll
const nav = document.getElementById('nav');
let lastScroll = 0;
window.addEventListener('scroll', () => {
  const y = window.scrollY;
  if (y > 100) nav.classList.add('is-scrolled');
  else nav.classList.remove('is-scrolled');
  lastScroll = y;
}, { passive: true });
```

- [ ] **Step 2: Verify in browser**

Reload. Scroll down past 100px. Expected: nav background gets more solid white, gains a hairline shadow. Scroll back to top: returns to softer glass.

- [ ] **Step 3: Commit**

```bash
git add templates/home.html
git commit -m "feat(landing): glass nav scroll state transition"
```

---

## Task 16: Responsive verification

**Files:**
- Modify: `templates/home.html` (only if breakpoints reveal layout bugs)

- [ ] **Step 1: Test at 4 widths in DevTools**

Open DevTools device toolbar. For each width, scroll the entire page and visually inspect every section. Make notes of layout issues.

- 375px (iPhone SE)
- 768px (iPad portrait)
- 1024px (iPad landscape)
- 1440px (desktop)

Expected behaviors:
- Hero: centered text, mockup card fills width on mobile
- Stats strip: stacks vertically <768px
- Pillars: stacks to 1 column <900px
- Module sections: text and mockup stack vertically <1024px
- Trust grid: 4→2→1 columns
- Footer: 4→2→1 columns
- Nav: hamburger menu <768px

- [ ] **Step 2: Fix any issues found**

For each issue, identify the section's CSS block in `<style>` and add or adjust the media query. Common fixes:
- Reduce padding on small screens: `padding: 4rem 1.25rem` at <768px
- Wrap long words: `word-wrap: break-word` on copy
- Reduce font sizes via `clamp()`

- [ ] **Step 3: Verify after fixes**

Re-scroll all 4 widths after any change.

- [ ] **Step 4: Commit**

```bash
git add templates/home.html
git commit -m "fix(landing): responsive adjustments across breakpoints"
```

If no changes were needed, skip the commit and proceed.

---

## Task 17: Accessibility audit

**Files:**
- Modify: `templates/home.html` (add ARIA attributes and alt text)

- [ ] **Step 1: Audit semantic HTML**

Verify each section uses `<section>`, headings descend logically (h1 only in hero, h2 in sections, h3 in cards). Open DevTools Accessibility tree to confirm.

- [ ] **Step 2: Add or verify ARIA labels**

- `<header class="nav" aria-label="Navegação principal">`
- `<nav class="nav-links" aria-label="Menu principal">`
- Each major `<section>` should have an `aria-labelledby` referencing its h2 id, OR an `aria-label` describing the section. Example for section 04: `<section class="section reveal" id="funcionalidades" aria-label="Três pilares da plataforma">`.

- [ ] **Step 3: Verify all interactive elements are keyboard-accessible**

Tab through the page from top to bottom. Every link, button, and form control should receive a visible focus indicator. If any element is missed, add `tabindex="0"` and a visible focus style.

- [ ] **Step 4: Color contrast spot-check**

Use DevTools or contrast checker on these pairs (must meet WCAG AA = 4.5:1 for body, 3:1 for large text):
- Cream text (#F5EFE2) on ink (#0F172A) → should pass
- Gold (#D4A547) on ink → should pass for large text only; do not use for body
- Muted (#6B7A96) on cream-light → should pass at 4.5:1
- Text-muted (#64748B) on white → should pass at 4.5:1

- [ ] **Step 5: Commit**

```bash
git add templates/home.html
git commit -m "a11y(landing): semantic HTML and ARIA labels"
```

---

## Task 18: Lighthouse audit and final cleanup

**Files:**
- Possibly modify: `templates/home.html` (per Lighthouse findings)

- [ ] **Step 1: Run Lighthouse**

Open the page in Chrome incognito, DevTools → Lighthouse → Mobile and Desktop → Performance, Accessibility, Best Practices, SEO.

Target scores:
- Performance ≥ 85
- Accessibility ≥ 95
- Best Practices ≥ 95
- SEO ≥ 95

- [ ] **Step 2: Fix flagged issues**

Common likely findings:
- Image alt text missing → add `alt=""` for decorative or descriptive alt for content images
- Background images on `<section>` make Lighthouse think there's no LCP candidate → ensure the headline is visible above the fold
- Tailwind CDN warning in production → acknowledge, document as backlog (out of scope per spec section 10)
- Render-blocking fonts → add `font-display=swap` (already included in the Google Fonts URL)

- [ ] **Step 3: Search for any em-dash that slipped through**

```bash
grep -n "—" templates/home.html
```

Expected: zero matches in user-facing copy. Section comment banners with `═══` characters are not em-dashes (they're U+2550 double horizontal). If any em-dash appears in copy, replace per the rule (period, comma, parentheses, or rewrite).

- [ ] **Step 4: Search for any banned terms**

```bash
grep -in "\bia\b\|inteligência artificial\|artificial intelligence" templates/home.html
```

Expected: zero matches in user-facing copy. (Internal HTML class names like `nav-cta` or attribute references are fine; only flag visible text.)

- [ ] **Step 5: Commit final cleanup**

```bash
git add templates/home.html
git commit -m "chore(landing): lighthouse and copy audit fixes"
```

---

## Task 19: Final verification and merge prep

- [ ] **Step 1: Smoke test the whole landing**

Start dev server. Walk through:
- Page loads in <3s
- All 12 sections render (count: nav + hero + stats + pillars + 4 modules + manifesto + duo + integrations + trust + cta + footer)
- 3 dark sections present: hero, manifesto, cta+footer
- Hover states on cards, nav links underline, gold CTA glow
- Reveal animation triggers on scroll
- Glass nav transitions on scroll
- Mobile menu opens and closes
- All CTAs link to `cadastro`, `login`, `home`, `privacidade`, `termos`
- No console errors

- [ ] **Step 2: Confirm legacy templates are isolated**

```bash
ls templates/legacy/
```

Expected: `home_pre_2026_05.html`, `preview_landing.html`, `preview_landing_light.html`. None referenced in `views.py` or `urls.py`.

- [ ] **Step 3: Final commit if any cleanup needed**

If any minor fixes came from the smoke test:

```bash
git add templates/home.html
git commit -m "feat(landing): final smoke test fixes"
```

If nothing changed, skip.

- [ ] **Step 4: Summary**

Landing implementation complete. Branch should now contain ~15-20 commits since the spec was merged, all under the `feat(landing): ...` or `fix(landing): ...` / `chore(landing): ...` / `a11y(landing): ...` prefix pattern.

Ready for the user to review the live result, request adjustments, and merge to main.
