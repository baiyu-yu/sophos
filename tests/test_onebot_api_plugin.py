"""onebot_api 插件（OneBot 11 通用接口调用）测试。"""

import unittest
from pathlib import Path

from sophos.adapter_router import AdapterRouter
from sophos.platform import ConversationKind, ConversationRef
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


class _FakePlatformStore:
    def __init__(self, kind: ConversationKind, external_id: str) -> None:
        self.kind = kind
        self.external_id = external_id

    async def get_conversation(self, conversation_id: int) -> ConversationRef:
        return ConversationRef(
            conversation_id=conversation_id,
            account_id=7,
            kind=self.kind,
            external_conversation_id=self.external_id,
            parent_conversation_id=None,
            display_name="测试群",
        )


class _FakeMessageService:
    def __init__(self, kind: ConversationKind = ConversationKind.GROUP) -> None:
        self.platform_store = _FakePlatformStore(kind, "1027612238")


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
            message_service=_FakeMessageService(),
        )
        await self.manager.init()
        self.context = {"adapter_capabilities": set(), "conversation_id": 2}

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

    async def test_metrics_actions_are_blocked(self) -> None:
        for action in ("send_msg", "delete_msg", "set_group_ban", "send_group_forward_msg"):
            result = await self.registry.execute("onebot_call", {"action": action}, self.context)
            self.assertFalse(result["ok"])
            self.assertIn("屏蔽", result["error"])
            self.assertIn("插件配置", result["error"])

    async def test_query_actions_are_allowed(self) -> None:
        for action in ("get_group_member_list", "get_group_list", "get_group_info"):
            result = await self.registry.execute("onebot_call", {"action": action}, self.context)
            self.assertTrue(result["ok"], msg=f"{action} 不应被屏蔽: {result}")
            self.assertEqual(result["data"]["action"], action)

    async def test_group_id_is_filled_from_current_conversation(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "set_group_card", "params": {"user_id": 10001, "card": "新名片"}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"]["group_id"], 1027612238)
        self.assertEqual(result["data"]["params"]["user_id"], 10001)

    async def test_explicit_group_id_is_preserved(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "get_group_member_list", "params": {"group_id": 999}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"], {"group_id": 999})

    async def test_private_conversation_leaves_group_id_empty(self) -> None:
        self.manager.runtime.message_service = _FakeMessageService(ConversationKind.DIRECT)
        result = await self.registry.execute(
            "onebot_call",
            {"action": "get_group_member_list", "params": {}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"], {})

    async def test_call_accepts_json_string_params(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "set_group_card", "params": '{"group_id": 1, "user_id": 2, "card": "x"}'},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"], {"group_id": 1, "user_id": 2, "card": "x"})

    async def test_invalid_params_are_rejected(self) -> None:
        result = await self.registry.execute(
            "onebot_call", {"action": "get_status", "params": "[1]"}, self.context
        )
        self.assertFalse(result["ok"])
        self.assertIn("params", result["error"])

    async def test_missing_action_is_rejected_by_registry(self) -> None:
        result = await self.registry.execute("onebot_call", {}, self.context)
        self.assertIn("缺少必填参数", result["error"])


if __name__ == "__main__":
    unittest.main()
