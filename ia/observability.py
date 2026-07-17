from __future__ import annotations

import logging
import json
from collections.abc import Sequence
from typing import Final

from django.conf import settings
from langfuse._client.attributes import LangfuseOtelSpanAttributes
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch


REDACTED_VALUE: Final = "[REDACTED]"
logger = logging.getLogger(__name__)
_LANGFUSE_CLIENT_INITIALIZED = False
_AGNO_INSTRUMENTED = False
_AGNO_INSTRUMENTOR = None

_ALLOWED_LANGFUSE_EXACT_ATTRIBUTES: Final[set[str]] = {
    LangfuseOtelSpanAttributes.ENVIRONMENT,
    LangfuseOtelSpanAttributes.RELEASE,
    LangfuseOtelSpanAttributes.VERSION,
    LangfuseOtelSpanAttributes.OBSERVATION_TYPE,
    LangfuseOtelSpanAttributes.OBSERVATION_LEVEL,
    LangfuseOtelSpanAttributes.OBSERVATION_MODEL,
    LangfuseOtelSpanAttributes.OBSERVATION_MODEL_PARAMETERS,
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

_LANGFUSE_NUMERIC_DETAIL_ATTRIBUTES: Final[set[str]] = {
    LangfuseOtelSpanAttributes.OBSERVATION_USAGE_DETAILS,
    LangfuseOtelSpanAttributes.OBSERVATION_COST_DETAILS,
}

_ALLOWED_OPENINFERENCE_EXACT_ATTRIBUTES: Final[set[str]] = {
    "agent.name",
    "agno.agent",
    "agno.agent.id",
    "agno.knowledge",
    "agno.run.id",
    "agno.tools",
    "graph.node.id",
    "graph.node.name",
    "input.mime_type",
    "llm.provider",
    "openinference.span.kind",
    "output.mime_type",
}

_ALLOWED_OPENINFERENCE_METRIC_PREFIXES: Final[tuple[str, ...]] = (
    "llm.token_count.",
)

_REDACTED_LANGFUSE_EXACT_ATTRIBUTES: Final[set[str]] = {
    LangfuseOtelSpanAttributes.OBSERVATION_INPUT,
    LangfuseOtelSpanAttributes.OBSERVATION_OUTPUT,
    LangfuseOtelSpanAttributes.OBSERVATION_METADATA,
    LangfuseOtelSpanAttributes.TRACE_INPUT,
    LangfuseOtelSpanAttributes.TRACE_OUTPUT,
    LangfuseOtelSpanAttributes.TRACE_METADATA,
    LangfuseOtelSpanAttributes.TRACE_USER_ID,
    LangfuseOtelSpanAttributes.TRACE_SESSION_ID,
}

_REDACTED_ATTRIBUTE_PREFIXES: Final[tuple[str, ...]] = (
    f"{LangfuseOtelSpanAttributes.OBSERVATION_METADATA}.",
    f"{LangfuseOtelSpanAttributes.TRACE_METADATA}.",
    "langfuse.experiment.",
)

# These gen_ai attributes are not yet verified against future OpenLIT/OpenTelemetry
# traffic. They remain conservative placeholders until a real trace requires them.
_ALLOWED_UNVERIFIED_EXACT_ATTRIBUTES: Final[set[str]] = {
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.operation.name",
    "gen_ai.system",
    "gen_ai.tool.name",
    "tool.name",
    "llm.model_name",
    "model",
    "latency_ms",
    "duration_ms",
}

_ALLOWED_UNVERIFIED_METRIC_PREFIXES: Final[tuple[str, ...]] = (
    "gen_ai.usage.",
    "gen_ai.token.",
    "llm.usage.",
)

_SENSITIVE_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "content",
    "input",
    "output",
    "message",
    "messages",
    "prompt",
    "completion",
    "document",
    "documents",
    "text",
    "chunk",
    "chunks",
)


def mask_otel_spans(params: MaskOtelSpansParams) -> MaskOtelSpansResult:
    """Redact OTEL span attributes with a closed allowlist.

    The Langfuse legacy ``mask`` hook does not inspect raw OTEL attributes
    emitted by third-party instrumentation. This function is intended for
    export-stage ``mask_otel_spans`` and fails closed: unknown attributes are
    redacted until they are explicitly reviewed and allowlisted.

    Current SDK limitation to verify in Fase 4: ``OtelSpanPatch`` only changes
    attributes, so this hook does not mask ``span.name`` or resource attributes.
    Confirm in the Langfuse dashboard that neither contains client data.
    """

    span_patches = {}

    for identifier, span in params.spans.items():
        set_attributes = {
            key: REDACTED_VALUE
            for key, value in span.attributes.items()
            if not _is_allowed_attribute(key, value)
        }
        set_attributes["masking.applied"] = bool(set_attributes)
        set_attributes["masking.policy"] = "closed-allowlist"

        span_patches[identifier] = OtelSpanPatch(set_attributes=set_attributes)

    return MaskOtelSpansResult(span_patches=span_patches)


def get_langfuse_callback_handler():
    if not settings.LANGFUSE_ENABLED:
        return None

    try:
        _ensure_langfuse_client()
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse tracing disabled for this run: %s", exc)
        return None


def ensure_agno_tracing() -> None:
    if not settings.LANGFUSE_ENABLED:
        return

    try:
        _ensure_langfuse_client()
    except Exception as exc:
        logger.warning("Agno tracing disabled for this run: %s", exc)


def _ensure_langfuse_client() -> None:
    global _LANGFUSE_CLIENT_INITIALIZED

    if _LANGFUSE_CLIENT_INITIALIZED:
        return

    from langfuse import Langfuse

    client = Langfuse(mask_otel_spans=mask_otel_spans)
    _LANGFUSE_CLIENT_INITIALIZED = True
    _ensure_agno_instrumentation(client)


def _ensure_agno_instrumentation(langfuse_client) -> None:
    """Patch Agno once so its OpenInference spans use Langfuse's masked provider."""
    global _AGNO_INSTRUMENTED, _AGNO_INSTRUMENTOR

    if _AGNO_INSTRUMENTED:
        return

    try:
        resources = getattr(langfuse_client, "_resources", None)
        tracer_provider = getattr(resources, "tracer_provider", None)
        if tracer_provider is None:
            logger.warning("Agno tracing skipped: Langfuse tracer provider is unavailable")
            return

        from openinference.instrumentation.agno import AgnoInstrumentor

        instrumentor = AgnoInstrumentor()
        instrumentor.instrument(tracer_provider=tracer_provider)
        _AGNO_INSTRUMENTOR = instrumentor
        _AGNO_INSTRUMENTED = True
    except Exception as exc:
        logger.warning("Agno tracing disabled for this process: %s", exc)


def _is_allowed_attribute(key: str, value: object) -> bool:
    normalized_key = key.lower()

    if key in _ALLOWED_LANGFUSE_EXACT_ATTRIBUTES:
        return True

    if key in _LANGFUSE_NUMERIC_DETAIL_ATTRIBUTES:
        return _is_numeric_detail_value(value)

    if key in _ALLOWED_OPENINFERENCE_EXACT_ATTRIBUTES:
        return True

    if key.startswith(_ALLOWED_OPENINFERENCE_METRIC_PREFIXES):
        return _is_metric_value(value)

    if key in _REDACTED_LANGFUSE_EXACT_ATTRIBUTES:
        return False

    if key.startswith(_REDACTED_ATTRIBUTE_PREFIXES):
        return False

    if key in _ALLOWED_UNVERIFIED_EXACT_ATTRIBUTES:
        return True

    if key.startswith(_ALLOWED_UNVERIFIED_METRIC_PREFIXES):
        return _is_metric_value(value)

    if any(fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS):
        return False

    if normalized_key.endswith(".tool.name"):
        return True

    return False


def _is_numeric_detail_value(value: object) -> bool:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return False

    if not isinstance(value, dict):
        return False

    return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value.values())


def _is_metric_value(value: object) -> bool:
    if isinstance(value, bool):
        return False

    if isinstance(value, (int, float)):
        return True

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)

    return False
