from langfuse._client.attributes import LangfuseOtelSpanAttributes
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


def _langfuse_attribute_constants():
    return {
        name: value
        for name, value in LangfuseOtelSpanAttributes.__dict__.items()
        if name.isupper()
    }


def _safe_value_for(attribute):
    if attribute == LangfuseOtelSpanAttributes.OBSERVATION_USAGE_DETAILS:
        return '{"input": 120, "output": 45, "total": 165}'
    if attribute == LangfuseOtelSpanAttributes.OBSERVATION_COST_DETAILS:
        return '{"input": 0.001, "output": 0.002, "total": 0.003}'
    if attribute == LangfuseOtelSpanAttributes.TRACE_TAGS:
        return '["jurisprudencia", "fase-4"]'
    if attribute == LangfuseOtelSpanAttributes.TRACE_PUBLIC:
        return False
    if attribute in {
        LangfuseOtelSpanAttributes.AS_ROOT,
        LangfuseOtelSpanAttributes.IS_APP_ROOT,
    }:
        return True
    return "valor-operacional"


def test_classifica_todas_as_constantes_reais_do_sdk_langfuse():
    pass_attributes = {
        LangfuseOtelSpanAttributes.ENVIRONMENT,
        LangfuseOtelSpanAttributes.RELEASE,
        LangfuseOtelSpanAttributes.VERSION,
        LangfuseOtelSpanAttributes.OBSERVATION_TYPE,
        LangfuseOtelSpanAttributes.OBSERVATION_LEVEL,
        LangfuseOtelSpanAttributes.OBSERVATION_MODEL,
        LangfuseOtelSpanAttributes.OBSERVATION_MODEL_PARAMETERS,
        LangfuseOtelSpanAttributes.OBSERVATION_USAGE_DETAILS,
        LangfuseOtelSpanAttributes.OBSERVATION_COST_DETAILS,
        LangfuseOtelSpanAttributes.OBSERVATION_COMPLETION_START_TIME,
        LangfuseOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE,
        LangfuseOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
        LangfuseOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
        LangfuseOtelSpanAttributes.TRACE_NAME,
        LangfuseOtelSpanAttributes.TRACE_TAGS,
        LangfuseOtelSpanAttributes.TRACE_PUBLIC,
        LangfuseOtelSpanAttributes.AS_ROOT,
        LangfuseOtelSpanAttributes.IS_APP_ROOT,
    }
    redact_attributes = {
        LangfuseOtelSpanAttributes.OBSERVATION_INPUT,
        LangfuseOtelSpanAttributes.OBSERVATION_OUTPUT,
        LangfuseOtelSpanAttributes.OBSERVATION_METADATA,
        LangfuseOtelSpanAttributes.TRACE_INPUT,
        LangfuseOtelSpanAttributes.TRACE_OUTPUT,
        LangfuseOtelSpanAttributes.TRACE_METADATA,
        LangfuseOtelSpanAttributes.TRACE_SESSION_ID,
        LangfuseOtelSpanAttributes.TRACE_USER_ID,
        LangfuseOtelSpanAttributes.EXPERIMENT_ID,
        LangfuseOtelSpanAttributes.EXPERIMENT_NAME,
        LangfuseOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
        LangfuseOtelSpanAttributes.EXPERIMENT_METADATA,
        LangfuseOtelSpanAttributes.EXPERIMENT_DATASET_ID,
        LangfuseOtelSpanAttributes.EXPERIMENT_ITEM_ID,
        LangfuseOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
        LangfuseOtelSpanAttributes.EXPERIMENT_ITEM_METADATA,
        LangfuseOtelSpanAttributes.EXPERIMENT_ITEM_ROOT_OBSERVATION_ID,
    }
    sdk_attributes = set(_langfuse_attribute_constants().values())

    assert len(sdk_attributes) == 35
    assert pass_attributes | redact_attributes == sdk_attributes
    assert pass_attributes.isdisjoint(redact_attributes)

    attributes = {
        attribute: _safe_value_for(attribute)
        for attribute in sdk_attributes
    }
    patched_attributes = _masked_attributes(attributes)

    for attribute in pass_attributes:
        assert patched_attributes[attribute] == attributes[attribute]

    for attribute in redact_attributes:
        assert patched_attributes[attribute] == REDACTED_VALUE


def test_classifica_atributos_reais_do_agno_openinference_0_1_27():
    pass_attributes = {
        "agent.name",
        "agno.agent",
        "agno.agent.id",
        "agno.knowledge",
        "agno.run.id",
        "agno.tools",
        "graph.node.id",
        "graph.node.name",
        "input.mime_type",
        "langfuse.internal.is_app_root",
        "llm.model_name",
        "llm.provider",
        "llm.token_count.completion",
        "llm.token_count.prompt",
        "openinference.span.kind",
        "output.mime_type",
    }
    redact_attributes = {
        "input.value",
        "llm.input_messages.0.message.content",
        "llm.input_messages.0.message.role",
        "llm.input_messages.1.message.content",
        "llm.input_messages.1.message.role",
        "llm.output_messages.0.message.content",
        "llm.output_messages.0.message.role",
        "llm.tools.0.tool.json_schema",
        "llm.tools.1.tool.json_schema",
        "llm.tools.2.tool.json_schema",
        "output.value",
        "session.id",
    }
    captured_attributes = {
        "agent.name": "Assistente Jurídico Virtual",
        "agno.agent": "Assistente Jurídico Virtual",
        "agno.agent.id": "assistente-juridico-virtual",
        "agno.knowledge": "Knowledge",
        "agno.run.id": "5e990685-cd8e-4129-837e-de9d556cf9c5",
        "agno.tools": ("search_datajud_api",),
        "graph.node.id": "1fb0b8afe10a19d0",
        "graph.node.name": "Assistente Jurídico Virtual",
        "input.mime_type": "application/json",
        "input.value": '{"messages": [{"content": "João Carlos Ferreira CPF 123.456.789-01"}]}',
        "langfuse.internal.is_app_root": True,
        "llm.input_messages.0.message.content": "System prompt juridico",
        "llm.input_messages.0.message.role": "system",
        "llm.input_messages.1.message.content": "João Carlos Ferreira CPF 123.456.789-01",
        "llm.input_messages.1.message.role": "user",
        "llm.model_name": "gpt-4o",
        "llm.output_messages.0.message.content": "OK.",
        "llm.output_messages.0.message.role": "assistant",
        "llm.provider": "OpenAI",
        "llm.token_count.completion": 3,
        "llm.token_count.prompt": 479,
        "llm.tools.0.tool.json_schema": '{"function": {"name": "search_datajud_api"}}',
        "llm.tools.1.tool.json_schema": '{"function": {"name": "search_knowledge_base"}}',
        "llm.tools.2.tool.json_schema": '{"function": {"name": "delete_memory"}}',
        "openinference.span.kind": "LLM",
        "output.mime_type": "application/json",
        "output.value": '{"messages": [{"role": "assistant", "content": "Ok."}]}',
        "session.id": "5511999990000",
    }

    assert len(captured_attributes) == 28
    assert pass_attributes | redact_attributes == set(captured_attributes)
    assert pass_attributes.isdisjoint(redact_attributes)

    patched_attributes = _masked_attributes(captured_attributes)

    for attribute in pass_attributes:
        assert patched_attributes[attribute] == captured_attributes[attribute]

    for attribute in redact_attributes:
        assert patched_attributes[attribute] == REDACTED_VALUE


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


def test_redige_output_estruturado_serializado():
    attributes = {
        "langfuse.observation.output": (
            '{"indice_risco": 82, "red_flags": ["João Carlos Ferreira '
            'tem CPF 123.456.789-01 e segredo processual"]}'
        ),
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["langfuse.observation.output"] == REDACTED_VALUE


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


def test_redige_identificadores_de_usuario_e_sessao():
    attributes = {
        "user.id": "42",
        "session.id": "+5511999990000",
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["user.id"] == REDACTED_VALUE
    assert patched_attributes["session.id"] == REDACTED_VALUE


def test_preserva_metricas_de_uso_e_custo():
    attributes = {
        "gen_ai.usage.input_tokens": 120,
        "gen_ai.usage.output_tokens": 45,
        "gen_ai.usage.total_tokens": 165,
        "langfuse.observation.usage_details": '{"input": 120, "output": 45, "total": 165}',
        "langfuse.observation.cost_details": '{"input": 0.001, "output": 0.002, "total": 0.003}',
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.usage.input_tokens"] == 120
    assert patched_attributes["gen_ai.usage.output_tokens"] == 45
    assert patched_attributes["gen_ai.usage.total_tokens"] == 165
    assert patched_attributes["langfuse.observation.usage_details"] == '{"input": 120, "output": 45, "total": 165}'
    assert patched_attributes["langfuse.observation.cost_details"] == '{"input": 0.001, "output": 0.002, "total": 0.003}'


def test_preserva_modelo_e_tool_name():
    attributes = {
        "gen_ai.request.model": "gpt-4.1-mini",
        "gen_ai.response.model": "gpt-4.1-mini",
        "gen_ai.tool.name": "search_datajud_api",
        "langfuse.observation.level": "DEFAULT",
        "langfuse.observation.model.name": "gpt-4.1-mini",
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.request.model"] == "gpt-4.1-mini"
    assert patched_attributes["gen_ai.response.model"] == "gpt-4.1-mini"
    assert patched_attributes["gen_ai.tool.name"] == "search_datajud_api"
    assert patched_attributes["langfuse.observation.level"] == "DEFAULT"
    assert patched_attributes["langfuse.observation.model.name"] == "gpt-4.1-mini"


def test_rejeita_bool_como_metrica():
    attributes = {
        "gen_ai.usage.cache_hit": True,
        "langfuse.observation.cost_details": '{"estimated": false}',
    }

    patched_attributes = _masked_attributes(attributes)

    assert patched_attributes["gen_ai.usage.cache_hit"] == REDACTED_VALUE
    assert patched_attributes["langfuse.observation.cost_details"] == REDACTED_VALUE
