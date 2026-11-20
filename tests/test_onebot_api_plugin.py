"""onebot_api 插件（OneBot 11 通用接口调用）测试。"""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sophos import media
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


class _FakeIdentity:
    def __init__(self, external_user_id: str) -> None:
        self.external_user_id = external_user_id


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

    async def get_identity_for_account(self, *, user_id: int, account_id: int):
        if user_id == 3 and account_id == 7:
            return _FakeIdentity("1004205930")
        return None


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

    def test_plugin_registers_tools(self) -> None:
        plugins = {item["name"]: item for item in self.manager.list_plugins()}
        self.assertIn("onebot_api", plugins)
        self.assertEqual(plugins["onebot_api"]["status"], "loaded")
        self.assertIn("onebot_call", plugins["onebot_api"]["tools"])
        self.assertIn("onebot_api_docs", plugins["onebot_api"]["tools"])

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

    async def test_internal_user_id_is_mapped_to_external(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "set_group_card", "params": {"user_id": 3, "card": "新名片"}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"]["user_id"], 1004205930)
        self.assertEqual(result["data"]["params"]["group_id"], 1027612238)

    async def test_unknown_user_id_passes_through(self) -> None:
        result = await self.registry.execute(
            "onebot_call",
            {"action": "set_group_card", "params": {"user_id": 999, "card": "x"}},
            self.context,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["params"]["user_id"], 999)

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

    async def test_unknown_action_is_rejected_with_suggestions(self) -> None:
        result = await self.registry.execute(
            "onebot_call", {"action": "get_group_member_lst"}, self.context
        )
        self.assertFalse(result["ok"])
        self.assertIn("未知 action", result["error"])
        self.assertIn("get_group_member_list", result["suggestions"])
        self.assertIn("onebot_api_docs", result["hint"])

    async def test_unknown_action_can_be_allowed_by_config(self) -> None:
        await self.manager.set_config("onebot_api", {"allow_unknown_actions": True})
        result = await self.registry.execute(
            "onebot_call", {"action": "custom_vendor_action", "params": {}}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["action"], "custom_vendor_action")

    async def test_action_alias_is_resolved(self) -> None:
        result = await self.registry.execute(
            "onebot_call", {"action": "send_group_sign", "params": {"group_id": 5}}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["action"], "set_group_sign")

    async def test_docs_lists_categories(self) -> None:
        result = await self.registry.execute("onebot_api_docs", {}, self.context)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total"], 222)
        self.assertIn("群管理", result["categories"])
        self.assertGreater(result["categories"]["群管理"], 10)
        self.assertIn("get_group_info", result["samples"]["群信息"])
        self.assertEqual(len(result["samples"]["群管理"]), 6)

    async def test_docs_describes_action_with_params_and_example(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"action": "set_group_card"}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["category"], "群管理")
        names = [param["name"] for param in result["params"]]
        self.assertEqual(names[:2], ["group_id", "user_id"])
        roles = {param["name"]: param.get("role") for param in result["params"]}
        self.assertEqual(roles["group_id"], "group_id")
        self.assertIn("内部 uid", result["example"]["params"]["user_id"])

    async def test_docs_marks_blocked_action(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"action": "send_group_msg"}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["builtin_equivalent"], "send_message")

    async def test_docs_searches_by_keyword(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"keyword": "公告"}, self.context
        )
        self.assertTrue(result["ok"])
        names = [item["name"] for item in result["actions"]]
        self.assertIn("_get_group_notice", names)
        self.assertLessEqual(result["returned"], 20)

    async def test_docs_filters_by_category_and_limit(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"category": "群文件", "limit": 3}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertLessEqual(result["returned"], 3)
        self.assertTrue(all(item["category"] == "群文件" for item in result["actions"]))

    async def test_docs_unknown_action_returns_suggestions(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"action": "get_group_member_lst"}, self.context
        )
        self.assertFalse(result["ok"])
        self.assertIn("get_group_member_list", result["suggestions"])

    async def test_catalog_source_is_reported(self) -> None:
        result = await self.registry.execute("onebot_api_docs", {}, self.context)
        self.assertIn("snowluma", result["source"].lower())

    async def test_avatar_accepts_chat_image_code(self) -> None:
        image_bytes = b"\x89PNG\r\n\x1a\nfake-avatar"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(media, "media_root", lambda: Path(tmp)):
            code = media.save_image_bytes(image_bytes, "image/png")
            self.assertIsNotNone(code)
            result = await self.registry.execute(
                "onebot_call",
                {"action": "set_qq_avatar", "params": {"file": code}},
                self.context,
            )
        self.assertTrue(result["ok"], msg=str(result))
        expected = "base64://" + base64.b64encode(image_bytes).decode("ascii")
        self.assertEqual(result["data"]["params"]["file"], expected)

    async def test_avatar_rejects_unknown_media_token(self) -> None:
        token = "00f003f007f01fe03e6024c0cf813f00fb0ffe13f642c49f080800000"
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(media, "media_root", lambda: Path(tmp)):
            result = await self.registry.execute(
                "onebot_call",
                {"action": "set_qq_avatar", "params": {"file": token}},
                self.context,
            )
        self.assertFalse(result["ok"])
        self.assertIn("图片编码", result["hint"])
        self.assertIn("file 标识", result["hint"])

    async def test_avatar_keeps_url(self) -> None:
        url = "https://example.com/avatar.png"
        result = await self.registry.execute(
            "onebot_call",
            {"action": "set_qq_avatar", "params": {"file": url}},
            self.context,
        )
        self.assertTrue(result["ok"], msg=str(result))
        self.assertEqual(result["data"]["params"]["file"], url)

    async def test_docs_reports_image_param_format(self) -> None:
        result = await self.registry.execute(
            "onebot_api_docs", {"action": "set_qq_avatar"}, self.context
        )
        self.assertTrue(result["ok"])
        self.assertIn("图片编码", result["params"][0]["format"])


if __name__ == "__main__":
    unittest.main()
