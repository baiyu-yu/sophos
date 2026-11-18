import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sophos import runtime_config
from sophos.api.routes.settings import routes


class RuntimeConfigValidationTests(unittest.TestCase):
    def test_known_keys_have_defaults_and_specs(self) -> None:
        self.assertEqual(set(runtime_config.get_defaults()), {spec["key"] for spec in runtime_config.list_specs()})

    def test_command_prefix_validation(self) -> None:
        self.assertEqual(runtime_config.validate_value("command_prefix", " ! "), "!")
        for value in ("", "    ", "abcd", "a b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_config.validate_value("command_prefix", value)

    def test_trigger_regex_validation(self) -> None:
        self.assertEqual(runtime_config.validate_value("trigger_regexes", ["^hi", " ", "在吗"]), ["^hi", "在吗"])
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", "not-a-list")
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", ["("])
        with self.assertRaises(ValueError):
            runtime_config.validate_value("trigger_regexes", ["x"] * 51)

    def test_timezone_validation(self) -> None:
        self.assertEqual(runtime_config.validate_value("timezone", "Asia/Shanghai"), "Asia/Shanghai")
        with self.assertRaises(ValueError):
            runtime_config.validate_value("timezone", "Mars/Base")

    def test_schema_must_keep_message_placeholder(self) -> None:
        schema = "[{{time}}] {{name}}：{{message}}"
        self.assertEqual(runtime_config.validate_value("llm_user_schema", schema), schema)
        with self.assertRaises(ValueError) as ctx:
            runtime_config.validate_value("llm_user_schema", "[{{time}}] {{name}}")
        self.assertIn("{{message}}", str(ctx.exception))

    def test_numeric_range_and_type_checks(self) -> None:
        self.assertEqual(runtime_config.validate_value("max_context_messages", 20), 20)
        with self.assertRaises(ValueError):
            runtime_config.validate_value("max_context_messages", 0)
        with self.assertRaises(ValueError):
            runtime_config.validate_value("max_context_messages", 2.5)
        with self.assertRaises(ValueError):
            runtime_config.validate_value("include_co_account_in_context", "yes")

    def test_nullable_temperature(self) -> None:
        self.assertIsNone(runtime_config.validate_value("llm_temperature", None))
        self.assertEqual(runtime_config.validate_value("llm_temperature", 0.3), 0.3)

    def test_unknown_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            runtime_config.validate_value("no_such_key", 1)


class SettingsRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        app = web.Application()
        app.router.add_routes(routes)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_list_returns_specs_groups_and_masks_secrets(self) -> None:
        with patch.dict(runtime_config._cache, {"tavily_api_key": "secret-value"}, clear=False):
            response = await self.client.get("/api/settings")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertTrue(payload["specs"])
        self.assertTrue(payload["groups"])
        self.assertEqual(payload["settings"]["tavily_api_key"], "********")
        schema_specs = {spec["key"]: spec for spec in payload["specs"]}
        self.assertIn("llm_user_schema", schema_specs)
        self.assertFalse(schema_specs["llm_user_schema"]["requires_restart"])
        self.assertTrue(schema_specs["log_max_bytes"]["requires_restart"])

    async def test_update_rejects_invalid_value(self) -> None:
        response = await self.client.put("/api/settings/command_prefix", json={"value": "abcd"})
        self.assertEqual(response.status, 400)
        self.assertIn("命令前缀", await response.text())

    async def test_update_persists_valid_value(self) -> None:
        with patch.object(runtime_config, "set_value", AsyncMock()) as set_value:
            response = await self.client.put("/api/settings/command_prefix", json={"value": "!"})
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload["value"], "!")
        self.assertIn("已更新", payload["message"])
        set_value.assert_awaited_once_with("command_prefix", "!")

    async def test_reset_restores_default(self) -> None:
        def _delete(key: str) -> bool:
            runtime_config._cache.pop(key, None)
            return True

        with (
            patch.object(runtime_config, "delete", AsyncMock(side_effect=_delete)),
            patch.dict(runtime_config._cache, {"command_prefix": "!"}, clear=False),
        ):
            response = await self.client.delete("/api/settings/command_prefix")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload["value"], ".")

    async def test_reset_unknown_key_is_rejected(self) -> None:
        response = await self.client.delete("/api/settings/no_such_key")
        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()
