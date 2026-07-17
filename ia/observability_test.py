from langfuse.types import MaskOtelSpansParams, OtelSpanData, OtelSpanIdentifier

from ia.observability import REDACTED_VALUE, mask_otel_spans


def _apply_patch(attributes, patch):
    patched = dict(attributes)
    for key in patch.delete_attributes:
        patched.pop(key, None)
    patched.update(patch.set_attributes)
    return patched


def _masked_attributes(attributes):
    identifier = OtelSpanIdentifier(
        trace_id="trace-123",
        span_id="span-456",
    )
    span = OtelSpanData(
        trace_id=identifier.trace_id,
        span_id=identifier.span_id,
        parent_span_id="parent-789",
        name="JurisprudenciaAI.run",
        instrumentation_scope_name="langfuse.langchain",
        instrumentation_scope_version="4.14.0",
        attributes=attributes,
        resource_attributes={},
    )
    result = mask_otel_spans(MaskOtelSpansParams(spans={identifier: span}))
    patch = result.span_patches[identifier]

    return _apply_patch(attributes, patch)


def test_redige_conteudo_sensivel_conhecido():
    attributes = {
        "gen_ai.prompt.0.content": "Sistema juridico do caso de João Carlos Ferreira",
        "gen_ai.prompt.3.content": "CPF 123.456.789-01 e petição inicial com tutela de urgencia",
        "gen_ai.completion.0.content": "Cliente deve ajuizar recurso imediatamente",
        "langfuse.observation.input": "E-mail joao@example.com e CNJ 1001234-56.2025.8.26.0100",
        "langfuse.observation.output": "Trecho de peticao com estrategia processual",
        "algum.campo.novo.content": "Campo novo desconhecido com João Carlos Ferreira",
    }

    patched_attributes = _masked_attributes(attributes)
    serialized_values = " ".join(str(value) for value in patched_attributes.values())

    assert "123.456.789-01" not in serialized_values
    assert "João Carlos Ferreira" not in serialized_values
    assert "petição inicial" not in serialized_values
    assert "1001234-56.2025.8.26.0100" not in serialized_values
    assert "joao@example.com" not in serialized_values
    assert patched_attributes["gen_ai.prompt.0.content"] == REDACTED_VALUE
    assert patched_attributes["gen_ai.prompt.3.content"] == REDACTED_VALUE
    assert patched_attributes["algum.campo.novo.content"] == REDACTED_VALUE


def test_redige_atributo_desconhecido_por_default_fechado():
    attributes = {
        "custom.field": "valor operacional aparentemente inocuo",
        "agno.session.metadata": "metadata de sessao",
        "db.statement": "select * from documentos",
        "user.id": "42",
        "retrieval.query": "consulta juridica",
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["custom.field"] == REDACTED_VALUE
    assert patched_attributes["agno.session.metadata"] == REDACTED_VALUE
    assert patched_attributes["db.statement"] == REDACTED_VALUE
    assert patched_attributes["user.id"] == REDACTED_VALUE
    assert patched_attributes["retrieval.query"] == REDACTED_VALUE


def test_preserva_metricas_de_uso_e_custo():
    attributes = {
        "gen_ai.usage.input_tokens": 120,
        "gen_ai.usage.output_tokens": 45,
        "gen_ai.usage.total_tokens": 165,
        "langfuse.observation.cost_details.total": 0.0012,
        "langfuse.observation.latency": 1.42,
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.usage.input_tokens"] == 120
    assert patched_attributes["gen_ai.usage.output_tokens"] == 45
    assert patched_attributes["gen_ai.usage.total_tokens"] == 165
    assert patched_attributes["langfuse.observation.cost_details.total"] == 0.0012
    assert patched_attributes["langfuse.observation.latency"] == 1.42


def test_preserva_modelo_e_tool_name():
    attributes = {
        "gen_ai.request.model": "gpt-4.1-mini",
        "gen_ai.response.model": "gpt-4.1-mini",
        "gen_ai.tool.name": "search_datajud_api",
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.request.model"] == "gpt-4.1-mini"
    assert patched_attributes["gen_ai.response.model"] == "gpt-4.1-mini"
    assert patched_attributes["gen_ai.tool.name"] == "search_datajud_api"


def test_rejeita_bool_como_metrica():
    attributes = {
        "gen_ai.usage.cache_hit": True,
        "langfuse.observation.cost_details.estimated": False,
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.usage.cache_hit"] == REDACTED_VALUE
    assert patched_attributes["langfuse.observation.cost_details.estimated"] == REDACTED_VALUE
