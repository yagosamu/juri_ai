# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server
python manage.py runserver

# Run async task worker (required for document processing pipeline)
python manage.py qcluster

# Apply migrations
python manage.py migrate

# Create new migrations after model changes
python manage.py makemigrations

# Django shell
python manage.py shell
```

Both `runserver` and `qcluster` must run simultaneously for full functionality — document uploads trigger background tasks via django-q that won't execute without the qcluster worker.

## Environment

Requires a `.env` file in the project root with:
- `OPENAI_API_KEY` — used by all three agents and LanceDB embeddings
- Google Calendar OAuth credentials file at the path referenced in `SecretariaAI.CREDENTIALS_PATH` (`ia/agents.py:120`)

## Architecture

### Multi-Agent System

Three specialized agents in `ia/agents.py` and `ia/agente_langchain.py`:

- **JuriAI** (Agno) — Legal Q&A with RAG over client documents + judicial process lookup via CNJ DataJud API. Built per-request with `knowledge_filters={'cliente_id': id}` to enforce per-client data isolation.
- **SecretariaAI** (Agno) — WhatsApp customer service + Google Calendar scheduling. Uses `session_id=phone_number` for per-contact conversation memory. Meetings restricted to 13h–18h.
- **JurisprudenciaAI** (Langchain + `gpt-4.1-mini`) — Structured risk analysis of legal documents. Returns `JurisprudenciaOutput` (Pydantic) with `indice_risco` (0–100), `erros_coerencia`, `riscos_juridicos`, `problemas_formatacao`, `red_flags`.

### Document Processing Pipeline

Upload → Django signal (`usuarios/signals.py`) → django-q `Chain` → sequential tasks in `ia/tasks.py`:
1. `ocr_and_markdown_file` — Docling converts PDF/image to markdown, saved to `Documentos.content`
2. `rag_documentos` — Inserts markdown into LanceDB (`documentos` table) with `cliente_id` metadata for RAG filtering

### Multi-Tenancy

Client data isolation is enforced at the RAG layer: documents are tagged with `cliente_id` on insert (`ia/tasks.py:24`) and queried with `knowledge_filters={'cliente_id': ...}` when building the JuriAI agent (`ia/views.py:44`). There is no row-level security at the database layer.

### Vector Databases (LanceDB)

Two separate tables in the `lancedb/` directory:
- `documentos` — client legal documents (used by JuriAI)
- `empresa` — company knowledge base (used by SecretariaAI)

Both use `OpenAIEmbedder` and are initialized as class-level attributes on their respective agent classes, meaning they're shared across all agent instances.

### Streaming Chat

`ia/views.py:stream_resposta` returns a `StreamingHttpResponse` that iterates `RunOutputEvent` from Agno. `RunEvent.run_content` chunks are yielded to the client; `RunEvent.tool_call_completed` events are persisted as `ContextRag` records for audit/display.

### WhatsApp Integration

`webhook_whatsapp` (`ia/views.py:131`) receives Evolution API webhooks. The `SendMessage` call is currently commented out — responses are returned as JSON but not yet sent back via WhatsApp. The Evolution API instance name must be configured when uncommenting.

## Key Design Decisions

- `JuriAI.knowledge` and `SecretariaAI.knowledge` are class-level attributes (not instance-level), so LanceDB connections are shared across requests.
- Agent memory is stored in the same `db.sqlite3` as Django, in separate tables (`my_memory_table`, `secretaria_memory_table`).
- `JurisprudenciaAI` is stateless (no memory, no RAG) — it only receives the document text from `Documentos.content`.
- The `SecretariaAI.INSTRUCTIONS` f-string is evaluated at class definition time, so `datetime.datetime.now()` is frozen at server startup; this is a known limitation.
