from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch


REDACTED_VALUE: Final = "[REDACTED]"

_ALLOWED_EXACT_ATTRIBUTES: Final[set[str]] = {
    "gen_ai.request.model",
    "gen_ai.response.model",
    "gen_ai.operation.name",
    "gen_ai.system",
    "gen_ai.tool.name",
    "tool.name",
    "llm.model_name",
    "model",
    "langfuse.observation.name",
    "langfuse.observation.type",
    "langfuse.observation.cost",
    "langfuse.observation.latency",
    "langfuse.observation.duration",
    "latency_ms",
    "duration_ms",
}

_ALLOWED_ATTRIBUTE_PREFIXES: Final[tuple[str, ...]] = (
    "gen_ai.usage.",
    "gen_ai.token.",
    "llm.usage.",
    "llm.token_count.",
    "langfuse.observation.usage_details.",
    "langfuse.observation.cost_details.",
    "langfuse.usage_details.",
    "langfuse.cost_details.",
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


def _is_allowed_attribute(key: str, value: object) -> bool:
    normalized_key = key.lower()

    if key in _ALLOWED_EXACT_ATTRIBUTES:
        return True

    if key.startswith(_ALLOWED_ATTRIBUTE_PREFIXES):
        return _is_metric_value(value)

    if any(fragment in normalized_key for fragment in _SENSITIVE_KEY_FRAGMENTS):
        return False

    if _is_latency_or_duration_metric(normalized_key, value):
        return True

    if "cost" in normalized_key and _is_metric_value(value):
        return True

    if normalized_key.endswith(".tool.name"):
        return True

    return False


def _is_latency_or_duration_metric(key: str, value: object) -> bool:
    return ("latency" in key or "duration" in key) and _is_metric_value(value)


def _is_metric_value(value: object) -> bool:
    if isinstance(value, bool):
        return False

    if isinstance(value, (int, float)):
        return True

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)

    return False
