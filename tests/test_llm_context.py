import unittest

from sophos.llm.context import apply_schema


class ApplySchemaTests(unittest.TestCase):
    def test_replaces_all_placeholders(self) -> None:
        rendered = apply_schema(
            "[{{time}}] #{{mid}} {{name}}({{uid}})：{{message}}",
            time="2026-11-18 11:32",
            mid="42",
            name="alice",
            uid="7",
            message="你好",
        )

        self.assertEqual(rendered, "[2026-11-18 11:32] #42 alice(7)：你好")

    def test_appends_message_when_placeholder_is_missing(self) -> None:
        # bullet 被 .env 的 # 注释截断后只剩时间戳，正文必须仍然出现
        rendered = apply_schema("[{{time}}]", time="2026-11-18 11:32", message="正文内容")

        self.assertEqual(rendered, "[2026-11-18 11:32] 正文内容")

    def test_missing_placeholder_without_message_keeps_template(self) -> None:
        rendered = apply_schema("[{{time}}]", time="2026-11-18 11:32")

        self.assertEqual(rendered, "[2026-11-18 11:32]")

    def test_describe_schema_uses_sample_values(self) -> None:
        described = apply_schema("[{{time}}] {{name}}：{{message}}", time="T", name="N", message="M")

        self.assertEqual(described, "[T] N：M")


if __name__ == "__main__":
    unittest.main()
