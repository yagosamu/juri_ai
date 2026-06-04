# JuriAI

**English version:** [README.md](README.md)

![Django](https://img.shields.io/badge/Django-6-092E20?logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17.5-4169E1?logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-Agents-412991?logo=openai&logoColor=white)
![Agno](https://img.shields.io/badge/Agno-2.5.5-111827)
![LangChain](https://img.shields.io/badge/LangChain-RAG-1C3C3C?logo=langchain&logoColor=white)
![LanceDB](https://img.shields.io/badge/LanceDB-Vector_DB-F97316)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-CDN-06B6D4?logo=tailwindcss&logoColor=white)

O JuriAI é uma plataforma SaaS jurídica para advogados autônomos e pequenos escritórios brasileiros. Ele reúne operação jurídica, gestão de clientes, financeiro, automação de documentos, cálculos judiciais e agentes de IA em uma única aplicação Django.

O objetivo é simples: reduzir tarefas operacionais repetitivas para que o advogado tenha mais tempo para estratégia jurídica, relacionamento com clientes e crescimento do escritório.

## Prévia do produto

**Landing page**

![Landing page do JuriAI](screenshots/landing-page.png)

**Dashboard operacional**

O dashboard principal oferece uma visão diária da operação do escritório: clientes ativos, documentos processados, análises de risco, prazos próximos e eventos de calendário em um só lugar.

![Dashboard do JuriAI](screenshots/dashboard-main.png)

### Análise Jurisprudencial de Risco

O JuriAI revisa documentos jurídicos com um pipeline estruturado de IA e transforma o resultado em um relatório acionável de risco. A análise destaca problemas de coerência, riscos jurídicos, falhas de formatação e red flags críticas, além de resumir a exposição do documento com score e classificação.

Isso ajuda o advogado a identificar rapidamente pontos frágeis antes de protocolar, revisar ou negociar uma peça jurídica.

![Análise jurisprudencial do JuriAI](screenshots/analise-jurisprudencial.png)

### Calculadora Judicial

A calculadora apoia fluxos jurídicos brasileiros com correção monetária e cenários de juros. Ela contempla índices de correção, modelos de juros, tabelas específicas de tribunais, cálculos trabalhistas, múltiplas parcelas, multas, honorários e comparação de cenários.

Os cálculos salvos podem ser vinculados aos processos e exportados, integrando a revisão financeira ao fluxo de gestão do caso.

![Calculadora judicial do JuriAI](screenshots/calculadora.png)

## Principais funcionalidades

- **Gestão de clientes e processos**: clientes, processos, prazos, andamentos, documentos e análises jurídicas em um só ambiente.
- **Chat jurídico com IA e RAG**: perguntas sobre documentos do cliente com filtro vetorial isolado por cliente.
- **Análise de risco documental**: revisão de petições e contratos com score de risco, red flags, problemas de coerência e formatação.
- **Geração de documentos com IA**: criação de minutas a partir de templates, dados do cliente, dados do processo e instruções do advogado.
- **Atendimento WhatsApp e CRM**: automação do primeiro contato, criação de leads, pipeline comercial e conversão em cliente.
- **Prazos e agenda**: controle de prazos, eventos no Google Calendar e alertas por e-mail.
- **Gestão financeira**: honorários, pagamentos, inadimplência, fluxo de caixa e exportação em PDF/Excel.
- **Calculadora judicial**: correção monetária, juros, tabelas de tribunais, cálculos trabalhistas, múltiplas parcelas e comparação de cenários.
- **Fluxos orientados à LGPD**: consentimento, termos, privacidade, exclusão de conta, auditoria e credenciais de terceiros criptografadas.

## Agentes de IA

| Agente | Stack | Função |
|---|---|---|
| **JuriAI** | Agno + LanceDB RAG | Perguntas jurídicas sobre documentos do cliente e consulta DataJud/CNJ |
| **SecretariaAI** | Agno + Evolution API + Google Calendar | Atendimento via WhatsApp, agendamento e criação de leads |
| **JurisprudenciaAI** | LangChain + OpenAI | Análise estruturada de risco em documentos jurídicos |
| **RedacaoAI** | Agno + OpenAI | Redação assistida por IA a partir de templates e contexto do caso |

## Integrações

- **OpenAI** para agentes de IA e embeddings
- **LanceDB** para busca vetorial local e RAG por cliente
- **Evolution API** para automação no WhatsApp
- **Google Calendar** para agendamento
- **CNJ DataJud** para dados de processos judiciais brasileiros
- **PostgreSQL** para banco de produção
- **SMTP** para alertas de prazos e financeiro
- **ReportLab, OpenPyXL e python-docx** para exportações em PDF, Excel e DOCX

O acesso ao DataJud/CNJ é usado apenas para consultar metadados públicos de processos judiciais brasileiros. A integração permanece visível no projeto porque não expõe segredos de clientes, credenciais privilegiadas ou dados jurídicos privados.

## Stack técnica

- **Backend**: Django 6, Python 3.13
- **Banco de dados**: PostgreSQL em produção, banco local configurável por ambiente
- **Tasks assíncronas**: django-q
- **Orquestração de IA**: Agno, LangChain
- **Banco vetorial**: LanceDB
- **Processamento de documentos**: Docling
- **Frontend**: Django templates + Tailwind CDN
- **Segurança e auditoria**: django-axes, django-auditlog, campos criptografados

## Licença

Este projeto é proprietário e todos os direitos são reservados. Veja [LICENSE](LICENSE).

Nenhuma permissão é concedida para copiar, modificar, distribuir, sublicenciar ou criar trabalhos derivados sem autorização prévia e por escrito do titular dos direitos autorais.
