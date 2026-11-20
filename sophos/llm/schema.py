"""JSON Schema transformations used at provider boundaries."""

from copy import deepcopy
from typing import Any


def close_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively disallow undeclared object properties without changing optionality."""
    result = deepcopy(schema)
    _close_objects(result)
    return result


def compile_openai_strict_schema(
    schema: dict[str, Any],
    *,
    optional_mode: str = "nullable",
) -> dict[str, Any]:
    """Compile canonical tool parameters to OpenAI strict-mode JSON Schema.

    Strict function calling requires every declared property to appear in
    ``required``. ``nullable`` mode preserves canonical optionality using null;
    ``required`` mode retains the original type for providers without null support.
    The canonical schema remains unchanged.
    """
    result = deepcopy(schema)
    _compile_openai_node(result, optional_mode=optional_mode)
    return result


def compile_openai_strict_tools(
    tools: list[dict[str, Any]],
    *,
    optional_mode: str = "nullable",
) -> list[dict[str, Any]]:
    """Return OpenAI tools with strict mode enabled and compliant parameters."""
    compiled = deepcopy(tools)
    for tool in compiled:
        if tool.get("type") != "function":
            continue
        function = tool.get("function", {})
        parameters = function.get("parameters")
        if isinstance(parameters, dict):
            function["parameters"] = compile_openai_strict_schema(
                parameters,
                optional_mode=optional_mode,
            )
        function["strict"] = True
    return compiled


def compile_gemini_safe_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rewrite OpenAI tools so Gemini-backed proxies can parse them.

    OpenAI-compatible gateways that forward requests to Gemini translate the
    JSON Schema themselves and choke on constructs that OpenAI accepts but
    Gemini's ``Schema`` message does not, e.g. ``type: ["string", "null"]``
    produced by strict mode or ``additionalProperties`` on free-form objects.
    This helper projects every ``parameters`` through
    :func:`compile_gemini_schema` and drops the OpenAI-only ``strict`` flag.
    """
    compiled: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") != "function":
            compiled.append(tool)
            continue
        function = dict(tool.get("function") or {})
        parameters = function.get("parameters")
        if isinstance(parameters, dict):
            function["parameters"] = compile_gemini_schema(parameters)
        function.pop("strict", None)
        compiled.append({"type": "function", "function": function})
    return compiled


def compile_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Compile canonical JSON Schema to Gemini's supported schema subset.

    Gemini's ``FunctionDeclaration.parameters`` (``google.ai.generativelanguage
    .v1beta.Schema``) only understands a small subset of JSON Schema.  Unknown
    keywords such as ``additionalProperties``, ``$defs`` or ``oneOf`` make the
    API reject the whole request (for example ``Invalid value at
    'request.tools[0].function_declarations[10].parameters.properties[3].value'
    (required), Starting an object on a scalar field``).  This projection keeps
    only supported keywords, flattens ``type`` arrays into ``nullable`` and
    guarantees declared object properties, without mutating the canonical tool
    definition.
    """
    projected = _project_gemini_node(schema)
    if not projected:
        return {"type": "object", "properties": {}}
    return projected


# 参考 google.ai.generativelanguage v1beta Schema 的字段。
_GEMINI_ALLOWED_KEYS = frozenset(
    {
        "type",
        "format",
        "title",
        "description",
        "nullable",
        "enum",
        "items",
        "properties",
        "required",
        "anyOf",
        "default",
        "example",
        "propertyOrdering",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "minProperties",
        "maxProperties",
        "minLength",
        "maxLength",
        "pattern",
    }
)


def strip_boundary_nulls(value: Any, canonical_schema: dict[str, Any]) -> Any:
    """Remove null placeholders introduced only by strict boundary compilation."""
    if isinstance(value, dict):
        properties = canonical_schema.get("properties", {})
        required = set(canonical_schema.get("required", []))
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            child_schema = properties.get(key, {}) if isinstance(properties, dict) else {}
            if item is None and key not in required:
                continue
            cleaned[key] = strip_boundary_nulls(item, child_schema)
        return cleaned
    if isinstance(value, list):
        item_schema = canonical_schema.get("items", {})
        return [strip_boundary_nulls(item, item_schema) for item in value]
    return value


def _project_gemini_node(schema: Any) -> dict[str, Any]:
    """把单个 JSON Schema 节点投影成 Gemini 支持的字段集合。"""
    if not isinstance(schema, dict):
        return {}

    source = dict(schema)
    # Gemini 的 Schema 没有 const / oneOf / allOf，用等价写法替代。
    if "const" in source and "enum" not in source:
        source["enum"] = [source.pop("const")]
    else:
        source.pop("const", None)
    if "oneOf" in source and "anyOf" not in source:
        source["anyOf"] = source.pop("oneOf")
    else:
        source.pop("oneOf", None)
    source.pop("allOf", None)

    node: dict[str, Any] = {}
    for key in _GEMINI_ALLOWED_KEYS:
        if key in source and source[key] is not None:
            node[key] = source[key]

    schema_type = node.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if isinstance(item, str) and item != "null"]
        if "null" in schema_type:
            node["nullable"] = True
        node["type"] = non_null[0] if non_null else "string"
    elif not isinstance(schema_type, str):
        node.pop("type", None)

    properties = node.get("properties")
    if isinstance(properties, dict) and properties:
        node["properties"] = {name: _project_gemini_node(child) for name, child in properties.items()}
        required = node.get("required")
        if isinstance(required, list):
            kept = [name for name in required if name in node["properties"]]
            if kept:
                node["required"] = kept
            else:
                node.pop("required", None)
    else:
        node.pop("properties", None)
        node.pop("required", None)

    items = node.get("items")
    if isinstance(items, dict):
        node["items"] = _project_gemini_node(items)
    elif isinstance(items, list):
        node.pop("items", None)

    branches = node.get("anyOf")
    if isinstance(branches, list):
        projected = [_project_gemini_node(branch) for branch in branches if isinstance(branch, dict)]
        if projected:
            node["anyOf"] = projected
        else:
            node.pop("anyOf", None)

    # 自由格式的 object（无 properties）会让部分代理转译出非法 Schema，
    # 统一补一个空的 properties 映射。
    if node.get("type") == "object" and "properties" not in node:
        node["properties"] = {}

    return node


def _close_objects(schema: Any) -> None:
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False
        for child in schema.get("properties", {}).values():
            _close_objects(child)
    if "items" in schema:
        _close_objects(schema["items"])
    for keyword in ("anyOf", "oneOf", "allOf"):
        for branch in schema.get(keyword, []):
            _close_objects(branch)


def _compile_openai_node(schema: Any, *, optional_mode: str) -> None:
    if not isinstance(schema, dict):
        return

    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        canonical_required = set(schema.get("required", []))
        schema["additionalProperties"] = False
        schema["required"] = list(properties)
        for name, child in properties.items():
            _compile_openai_node(child, optional_mode=optional_mode)
            if name not in canonical_required and optional_mode == "nullable":
                properties[name] = _make_nullable(child)

    if "items" in schema:
        _compile_openai_node(schema["items"], optional_mode=optional_mode)
    for keyword in ("anyOf", "oneOf", "allOf"):
        for branch in schema.get(keyword, []):
            _compile_openai_node(branch, optional_mode=optional_mode)


def _make_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)
    schema_type = result.get("type")
    if isinstance(schema_type, str):
        result["type"] = [schema_type, "null"]
        return result
    if isinstance(schema_type, list):
        if "null" not in schema_type:
            result["type"] = [*schema_type, "null"]
        return result
    if "anyOf" in result:
        if not any(branch == {"type": "null"} for branch in result["anyOf"]):
            result["anyOf"].append({"type": "null"})
        return result
    return {"anyOf": [result, {"type": "null"}]}
