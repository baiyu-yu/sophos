"""上游 Gemini 拒绝 OpenAI 风格工具 schema 时的自动降级重试。"""

import unittest
from typing import Any

from sophos.llm.openai_compat import OpenAICompatProvider, _is_gemini_schema_error
from sophos.llm.provider import ProviderRequestOptions
from sophos.llm.schema import compile_gemini_safe_tools

# 严格模式编译后的工具：可选字段是 type 数组，自由对象带 additionalProperties。
STRICT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "demo",
        "description": "demo tool",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "动作"},
                "payload": {
                    "type": "object",
                    "description": "任意参数",
                    "additionalProperties": True,
                },
                "reason": {"type": ["string", "null"], "description": "原因"},
            },
            "required": ["action", "payload", "reason"],
            "additionalProperties": False,
        },
    },
}

GEMINI_ERROR = (
    "LLM API error 400: {\"error\":{\"message\":\"Invalid value at "
    "'request.tools[0].function_declarations[11].parameters.properties[3].value' (required), "
    'Starting an object on a scalar field","code":400}}'
)


class FakeSession:
    """只用于避免 OpenAICompatProvider 创建真实 aiohttp session。"""


class GeminiFallbackTests(unittest.IsolatedAsyncioTestCase):
    def _provider(self) -> OpenAICompatProvider:
        provider = OpenAICompatProvider(base_url="https://gateway.example/v1", api_key="k", model="m")
        provider._get_session = lambda: FakeSession()  # type: ignore[method-assign]
        return provider

    async def test_retries_with_gemini_projection_on_schema_error(self) -> None:
        provider = self._provider()
        payloads: list[dict[str, Any]] = []

        async def fake_send(session, url, payload, *, use_stream, on_first_token):
            payloads.append(payload)
            if len(payloads) == 1:
                raise RuntimeError(GEMINI_ERROR)
            return {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}

        provider._send = fake_send  # type: ignore[method-assign]

        response = await provider.chat(
            [{"role": "user", "content": "hi"}],
            tools=[STRICT_TOOL],
            request_options=ProviderRequestOptions(tool_choice="required"),
        )

        self.assertEqual(response["message"]["content"], "ok")
        self.assertEqual(len(payloads), 2)
        self.assertTrue(payloads[0]["tools"][0]["function"]["strict"])
        retried = payloads[1]["tools"][0]["function"]
        self.assertNotIn("strict", retried)
        parameters = retried["parameters"]
        self.assertNotIn("additionalProperties", parameters)
        self.assertEqual(parameters["properties"]["reason"]["type"], "string")
        self.assertTrue(parameters["properties"]["reason"]["nullable"])
        self.assertNotIn("additionalProperties", parameters["properties"]["action"])

    async def test_next_call_uses_projection_without_retry(self) -> None:
        provider = self._provider()
        payloads: list[dict[str, Any]] = []
        state = {"failed": False}

        async def fake_send(session, url, payload, *, use_stream, on_first_token):
            payloads.append(payload)
            if not state["failed"]:
                state["failed"] = True
                raise RuntimeError(GEMINI_ERROR)
            return {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}

        provider._send = fake_send  # type: ignore[method-assign]
        await provider.chat([{"role": "user", "content": "hi"}], tools=[STRICT_TOOL])

        payloads.clear()
        await provider.chat([{"role": "user", "content": "hi"}], tools=[STRICT_TOOL])

        self.assertEqual(len(payloads), 1)
        self.assertNotIn("strict", payloads[0]["tools"][0]["function"])

    async def test_other_400_is_not_retried(self) -> None:
        provider = self._provider()
        payloads: list[dict[str, Any]] = []

        async def fake_send(session, url, payload, *, use_stream, on_first_token):
            payloads.append(payload)
            raise RuntimeError("LLM API error 400: model not found")

        provider._send = fake_send  # type: ignore[method-assign]

        with self.assertRaises(RuntimeError):
            await provider.chat([{"role": "user", "content": "hi"}], tools=[STRICT_TOOL])

        self.assertEqual(len(payloads), 1)

    async def test_request_without_tools_is_not_retried(self) -> None:
        provider = self._provider()
        payloads: list[dict[str, Any]] = []

        async def fake_send(session, url, payload, *, use_stream, on_first_token):
            payloads.append(payload)
            raise RuntimeError(GEMINI_ERROR)

        provider._send = fake_send  # type: ignore[method-assign]

        with self.assertRaises(RuntimeError):
            await provider.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(len(payloads), 1)


class GeminiSafeToolsTests(unittest.TestCase):
    def test_tools_are_projected_and_strict_is_dropped(self) -> None:
        compiled = compile_gemini_safe_tools([STRICT_TOOL])

        function = compiled[0]["function"]
        self.assertNotIn("strict", function)
        self.assertNotIn("additionalProperties", function["parameters"])
        self.assertEqual(compiled[0]["type"], "function")
        self.assertEqual(compiled[0]["function"]["name"], "demo")

    def test_schema_error_detection(self) -> None:
        self.assertTrue(_is_gemini_schema_error(RuntimeError(GEMINI_ERROR)))
        self.assertFalse(_is_gemini_schema_error(RuntimeError("LLM API error 500: boom")))


if __name__ == "__main__":
    unittest.main()
