"""onebot_api 插件（OneBot 11 通用接口调用）测试。"""

import unittest
from pathlib import Path

from sophos.adapter_router import AdapterRouter
from sophos.plugins import MemoryPluginStateStore, PluginManager
from sophos.toolkit.runtime import build_registry

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


class _FakeAdapter:
    binding_id = 1
    account_id = 7
    capabilities = frozenset()

    @property
    def protocol_name(self) -> str:
        return "fake"

    async def call_protocol_api(self, action, params=None, *, timeout=None):
        return {"action": action, "params": params, "timeout": timeout}


class OneBotApiPluginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.registry = build_registry()
        self.router = AdapterRouter()
        self.router.register(_FakeAdapter())
        self.manager = PluginManager(
            registry=self.registry,
            plugin_dir=PLUGINS_DIR,
            state_store=MemoryPluginStateStore(),
            adapter_router=self.router,
        )
        await self.manager.init()
        self.context = {"adapter_capabilities": set()}

    async def asyncTearDown(self) -> None:
        await self.manager.close()

    def test_plugin_registers_onebot_call(self) -> None:
        plugins = {item["name"]: item for item in self.manager.list_plugins()}
        self.assertIn("onebot_api", plugins)
        self.assertEqual(plugins["onebot_api"]["status"], "loaded")
        self.assertIn("onebot_call", plugins["onebot_api"]["tools"])

    async def test_call_forwards_action_and_params(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "get_group_list", "params": {"no_cache": True}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["action"], "get_group_list")
        self.assertEqual(result["data"]["params"], {"no_cache": True})

    async def test_builtin_action_is_blocked(self) -> None:
        for action in ("send_msg", "delete_msg", "get_group_member_list", "set_group_ban"):
            result = await self.registry.execute("onebot_call", {"action": action}, self.context)
            self.assertFalse(result["ok"])
            self.assertIn("屏蔽", result["error"])

    async def test_invalid_params_are_rejected(self) -> None:
        result = await self.registry.execute(
            "onebot_call", {"action": "get_status", "params": [1]}, self.context
        )
        self.assertFalse(result["ok"])
        self.assertIn("params", result["error"])

    async def test_missing_action_is_rejected_by_registry(self) -> None:
        result = await self.registry.execute("onebot_call", {}, self.context)
        self.assertIn("缺少必填参数", result["error"])


if __name__ == "__main__":
    unittest.main()
