"""Encode a caller's response JSON schema as each provider's strict structured output.

``complete_live_prompt`` is the one path every raw-HTTP caller (benchmark
solvers, corpus labeling panels, judges) uses to ask a provider for JSON. When a
caller supplies a schema, the provider must enforce it natively; a schema that
reaches the model only as prompt prose is not enforced. On 2026-09-30/10-01
gpt-6.1-sol, given a findings schema only as prose, answered an enum field as
a JSON list on 1,929 of 3,116 findings.

Each provider's strict mode accepts a narrower JSON Schema than callers write,
so this module adapts the schema and refuses, before any request is sent, a
schema the provider cannot enforce exactly:

* OpenAI (Responses ``text.format``, ``strict: true``) needs an object root,
  every property listed in ``required`` and ``additionalProperties: false``.
  Optional properties therefore become required and nullable. Callers must
  read ``null`` as absent.
* Anthropic (Messages ``output_config.format``) needs an object root and
  ``additionalProperties: false``, and rejects numeric and string bounds. The
  Anthropic SDK's own ``transform_schema`` moves those bounds into the
  description, so the caller's parser stays authoritative for them.

Both refuse a free-form object (no ``properties`` or ``additionalProperties``
other than ``false``): strict mode would force it to ``{}``, a silent change of
meaning.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, cast

OPENAI_RESPONSE_FORMAT_NAME: Final = "legalforecast_response"

_SUBSCHEMA_LIST_KEYS: Final = ("anyOf", "oneOf", "allOf", "prefixItems")
_SUBSCHEMA_MAP_KEYS: Final = ("$defs", "definitions")


class StructuredOutputSchemaError(ValueError):
    """The provider's strict structured output cannot enforce this schema."""


def native_schema_fields(
    provider: str, schema: Mapping[str, Any] | None
) -> dict[str, object]:
    """Return the request fields that make ``provider`` enforce ``schema``.

    Covers the providers whose request builders take these fields (OpenAI
    Responses, Anthropic Messages direct or on Bedrock). Gemini and the
    OpenAI-compatible providers encode their own native field in their builders.
    """

    if schema is None:
        return {}
    normalized = provider.strip().lower()
    if normalized == "openai":
        return {"text": openai_text_format(schema)}
    if normalized == "anthropic":
        return {"output_config": {"format": anthropic_output_format(schema)}}
    return {}


def openai_text_format(schema: Mapping[str, Any]) -> dict[str, object]:
    """Return the Responses API ``text`` field that enforces ``schema`` strictly."""

    return {
        "format": {
            "type": "json_schema",
            "name": OPENAI_RESPONSE_FORMAT_NAME,
            "schema": openai_strict_json_schema(schema),
            "strict": True,
        }
    }


def anthropic_output_format(schema: Mapping[str, Any]) -> dict[str, object]:
    """Return the Messages API ``output_config.format`` value for ``schema``."""

    _require_enforceable(schema, provider="Anthropic")
    try:
        from anthropic import transform_schema
    except ImportError as exc:  # anthropic is an optional extra of this package
        raise StructuredOutputSchemaError(
            "Anthropic strict structured output needs the anthropic package "
            "(install the managed-anthropic extra)"
        ) from exc
    return {"type": "json_schema", "schema": transform_schema(dict(schema))}


def openai_strict_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``schema`` in OpenAI strict form; optional properties become nullable."""

    _require_enforceable(schema, provider="OpenAI")
    return _openai_strict(schema)


def _openai_strict(schema: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(schema)
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        required = set(cast(list[str], schema.get("required", [])))
        converted: dict[str, Any] = {}
        for name, child in cast(Mapping[str, Mapping[str, Any]], properties).items():
            strict_child = _openai_strict(child)
            converted[name] = (
                strict_child if name in required else _nullable(strict_child)
            )
        result["properties"] = converted
        result["required"] = list(converted)
        result["additionalProperties"] = False
    items = schema.get("items")
    if isinstance(items, Mapping):
        result["items"] = _openai_strict(cast(Mapping[str, Any], items))
    for key in _SUBSCHEMA_LIST_KEYS:
        options = schema.get(key)
        if isinstance(options, list):
            result[key] = [
                _openai_strict(option)
                for option in cast(list[Mapping[str, Any]], options)
            ]
    for key in _SUBSCHEMA_MAP_KEYS:
        definitions = schema.get(key)
        if isinstance(definitions, Mapping):
            result[key] = {
                name: _openai_strict(definition)
                for name, definition in cast(
                    Mapping[str, Mapping[str, Any]], definitions
                ).items()
            }
    return result


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    kind = schema.get("type")
    if kind is None:
        return {"anyOf": [schema, {"type": "null"}]}
    kinds = list(cast(list[str], kind)) if isinstance(kind, list) else [kind]
    result = dict(schema)
    if "null" not in kinds:
        result["type"] = [*kinds, "null"]
    enum = schema.get("enum")
    if isinstance(enum, list) and None not in enum:
        result["enum"] = [*cast(list[object], enum), None]
    return result


def _require_enforceable(schema: Mapping[str, Any], *, provider: str) -> None:
    if schema.get("type") != "object":
        raise StructuredOutputSchemaError(
            f"{provider} strict structured output needs an object root schema; "
            "wrap the value in an object"
        )
    _refuse_free_form_objects(schema, provider=provider, path="$")


def _refuse_free_form_objects(
    schema: Mapping[str, Any], *, provider: str, path: str
) -> None:
    kind = schema.get("type")
    is_object = kind == "object" or (isinstance(kind, list) and "object" in kind)
    if is_object:
        additional = schema.get("additionalProperties", False)
        if additional is not False or not isinstance(schema.get("properties"), Mapping):
            raise StructuredOutputSchemaError(
                f"{provider} strict structured output cannot enforce the free-form "
                f"object at {path}; list its properties with "
                "additionalProperties false"
            )
    for name, child in _children(schema):
        _refuse_free_form_objects(child, provider=provider, path=f"{path}.{name}")


def _children(schema: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    children: list[tuple[str, Mapping[str, Any]]] = []
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        children.extend(cast(Mapping[str, Mapping[str, Any]], properties).items())
    items = schema.get("items")
    if isinstance(items, Mapping):
        children.append(("[]", cast(Mapping[str, Any], items)))
    for key in _SUBSCHEMA_LIST_KEYS:
        options = schema.get(key)
        if isinstance(options, list):
            children.extend(
                (f"{key}[{index}]", option)
                for index, option in enumerate(cast(list[Mapping[str, Any]], options))
            )
    for key in _SUBSCHEMA_MAP_KEYS:
        definitions = schema.get(key)
        if isinstance(definitions, Mapping):
            children.extend(
                (f"{key}.{name}", definition)
                for name, definition in cast(
                    Mapping[str, Mapping[str, Any]], definitions
                ).items()
            )
    return children


__all__ = [
    "OPENAI_RESPONSE_FORMAT_NAME",
    "StructuredOutputSchemaError",
    "anthropic_output_format",
    "native_schema_fields",
    "openai_strict_json_schema",
    "openai_text_format",
]
