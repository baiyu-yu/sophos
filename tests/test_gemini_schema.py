"""Gemini FunctionDeclaration schema 投影测试。"""

from __future__ import annotations

import unittest
from typing import Any

from sophos.llm.schema import _GEMINI_ALLOWED_KEYS, compile_gemini_schema
from sophos.tools import load_builtin_tools


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for key in ("properties", "items"):
            child = node.get(key)
            if isinstance(child, dict):
                if key == "properties":
                    for value in child.values():
                        yield from _walk(value)
                else:
                    yield from _walk(child)
        for branch in node.get("anyOf", []) or []:
            yield from _walk(branch)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


class GeminiSchemaProjectionTests(unittest.TestCase):
    def test_drops_unsupported_keywords(self) -> None:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "$defs": {"x": {"type": "string"}},
            "properties": {
                "a": {"type": "string", "pattern": "^x$", "examples": ["x"]},
                "b": {"allOf": [{"type": "string"}]},
            },
            "required": ["a", "missing"],
        }
        compiled = compile_gemini_schema(schema)
        self.assertEqual(set(compiled), {"type", "properties", "required"})
        self.assertEqual(compiled["required"], ["a"])
        self.assertNotIn("examples", compiled["properties"]["a"])

    def test_type_array_becomes_nullable(self) -> None:
        compiled = compile_gemini_schema({"type": ["string", "null"], "description": "x"})
        self.assertEqual(compiled["type"], "string")
        self.assertTrue(compiled["nullable"])

    def test_const_and_oneof_are_translated(self) -> None:
        compiled = compile_gemini_schema(
            {
                "oneOf": [{"type": "string"}, {"type": "integer"}],
                "properties": {"mode": {"const": "fast"}},
                "type": "object",
            }
        )
        self.assertEqual([branch["type"] for branch in compiled["anyOf"]], ["string", "integer"])
        self.assertEqual(compiled["properties"]["mode"]["enum"], ["fast"])

    def test_free_form_object_gets_empty_properties(self) -> None:
        compiled = compile_gemini_schema(
            {"type": "object", "properties": {"payload": {"type": "object"}}}
        )
        self.assertEqual(compiled["properties"]["payload"]["properties"], {})

    def test_all_builtin_tool_schemas_are_gemini_safe(self) -> None:
        for tool in load_builtin_tools():
            compiled = compile_gemini_schema(tool.parameters)
            for node in _walk(compiled):
                unknown = set(node) - _GEMINI_ALLOWED_KEYS
                self.assertFalse(unknown, f"{tool.name}: unsupported keys {unknown}")
                self.assertNotIn("additionalProperties", node)
                if node.get("type") == "object":
                    self.assertIn("properties", node, f"{tool.name}: object without properties")


if __name__ == "__main__":
    unittest.main()
