"""Tests for compact command-prefix normalisation."""

import unittest

from sophos import runtime_config
from sophos.pipeline import _normalize_command_prefix


class CommandPrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_config._cache.pop("command_prefix", None)

    def tearDown(self) -> None:
        runtime_config._cache.pop("command_prefix", None)

    def test_ascii_prefix_is_preserved(self) -> None:
        self.assertEqual(_normalize_command_prefix(".help"), ".help")

    def test_fullwidth_period_becomes_ascii_dot(self) -> None:
        self.assertEqual(_normalize_command_prefix("。help"), ".help")
        self.assertEqual(_normalize_command_prefix(" ．bot on"), ".bot on")
        self.assertEqual(_normalize_command_prefix("｡ping"), ".ping")

    def test_custom_prefix_is_translated(self) -> None:
        runtime_config._cache["command_prefix"] = "!"
        self.assertEqual(_normalize_command_prefix("!help"), ".help")
        self.assertEqual(_normalize_command_prefix(" !bot on"), ".bot on")
        # 半角点仍然兼容
        self.assertEqual(_normalize_command_prefix(".help"), ".help")

    def test_plain_text_is_untouched(self) -> None:
        self.assertEqual(_normalize_command_prefix("你好"), "你好")
        self.assertEqual(_normalize_command_prefix(""), "")

    def test_fullwidth_period_in_the_middle_is_untouched(self) -> None:
        self.assertEqual(_normalize_command_prefix("你好。世界"), "你好。世界")


if __name__ == "__main__":
    unittest.main()
