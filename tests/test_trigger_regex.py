"""触发正则匹配与配置校验测试。"""

import re
import unittest

from sophos import runtime_config, trigger


class TriggerRegexTests(unittest.TestCase):
    def tearDown(self) -> None:
        trigger.invalidate_regex_cache()

    def test_match_hit_returns_pattern(self) -> None:
        self.assertEqual(trigger.match_regex("有人在吗", ["^有", "吗$"]), "^有")

    def test_match_miss_returns_none(self) -> None:
        self.assertIsNone(trigger.match_regex("今天天气不错", ["^有", "帮我看看"]))

    def test_invalid_pattern_is_skipped(self) -> None:
        patterns = ["(", "帮我看看"]
        self.assertEqual(trigger.match_regex("帮我看看这个", patterns), "帮我看看")

    def test_only_invalid_patterns_returns_none(self) -> None:
        self.assertIsNone(trigger.match_regex("随便说点什么", ["(", "["]))

    def test_compile_regexes_raises_on_invalid(self) -> None:
        with self.assertRaises(re.error):
            trigger.compile_regexes(["("])


class TriggerRegexValidationTests(unittest.TestCase):
    def test_accepts_list_and_strips_blank_lines(self) -> None:
        value = runtime_config.validate_value("trigger_regexes", ["  ^有  ", "", "   ", "吗$"])
        self.assertEqual(value, ["^有", "吗$"])

    def test_rejects_non_list(self) -> None:
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", "^有")

    def test_rejects_invalid_pattern(self) -> None:
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", ["("])

    def test_rejects_too_many_patterns(self) -> None:
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", [f"p{i}" for i in range(51)])

    def test_rejects_overlong_pattern(self) -> None:
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", ["x" * 201])


if __name__ == "__main__":
    unittest.main()
