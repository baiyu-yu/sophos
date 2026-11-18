import unittest

from sophos.llm.tool_text import call_from_text, normalize_tool_arguments, parse_textual_tool_call


class ParseTextualToolCallTests(unittest.TestCase):
    def test_python_style_call_with_trailing_text(self) -> None:
        call = parse_textual_tool_call("send_message(reply_to_message_id=2708) 伟大的生物一直都很对劲，要夸奖！")
        self.assertIsNotNone(call)
        assert call is not None
        self.assertEqual(call.name, "send_message")
        self.assertEqual(call.arguments, {"reply_to_message_id": 2708})
        self.assertEqual(call.text_argument(), "伟大的生物一直都很对劲，要夸奖！")

    def test_json_arguments(self) -> None:
        call = parse_textual_tool_call('send_message({"text": "hi", "reply_to_message_id": 3})')
        assert call is not None
        self.assertEqual(call.arguments, {"text": "hi", "reply_to_message_id": 3})
        self.assertEqual(call.text_argument(), "hi")

    def test_json_without_parentheses(self) -> None:
        call = parse_textual_tool_call('send_message{"text": "hi"}')
        assert call is not None
        self.assertEqual(call.arguments, {"text": "hi"})

    def test_positional_text(self) -> None:
        call = parse_textual_tool_call("send_message(你好呀)")
        assert call is not None
        self.assertEqual(call.text_argument(), "你好呀")

    def test_call_with_only_identifier_is_ignored(self) -> None:
        self.assertIsNone(parse_textual_tool_call("send_message 是发送消息的工具"))
        self.assertIsNone(parse_textual_tool_call("今天天气不错（真的）"))

    def test_call_from_text_normalizes_message_alias(self) -> None:
        call = call_from_text('send_message({"message": "用 message 传的正文"})')
        assert call is not None
        self.assertEqual(call.arguments.get("text"), "用 message 传的正文")
        self.assertEqual(call.text_argument(), "用 message 传的正文")

    def test_call_from_text_keeps_explicit_text(self) -> None:
        call = call_from_text('send_message({"text": "正文", "content": "别名"})')
        assert call is not None
        self.assertEqual(call.arguments.get("text"), "正文")


class NormalizeToolArgumentsTests(unittest.TestCase):
    def test_send_message_alias_is_moved_to_text(self) -> None:
        self.assertEqual(
            normalize_tool_arguments("send_message", {"content": "正文", "reply_to_message_id": 1}),
            {"text": "正文", "reply_to_message_id": 1},
        )

    def test_other_tools_are_untouched(self) -> None:
        self.assertEqual(normalize_tool_arguments("web_search", {"content": "x"}), {"content": "x"})


if __name__ == "__main__":
    unittest.main()
