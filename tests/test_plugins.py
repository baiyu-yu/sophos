"""插件系统测试：发现、加载、工具注册、启停、配置与 origin 隔离。"""

import unittest
from pathlib import Path
from typing import Any

from sophos.plugins import MemoryPluginStateStore, PluginManager
from sophos.toolkit.registry import ORIGIN_BUILTIN, ToolRegistry, plugin_origin

_DEMO_PLUGIN = '''
from sophos.plugins import PluginMetadata


class Demo:
    metadata = PluginMetadata(
        name="demo",
        version="1.2.3",
        description="demo plugin",
        default_config={"prefix": "a"},
    )

    def setup(self, api):
        @api.tool(
            name="demo_ping",
            description="ping",
            parameters={"type": "object", "properties": {}},
        )
        async def ping(params, context):
            return {"pong": api.config.get("prefix")}

    def teardown(self):
        pass


PLUGIN = Demo()
'''

_RELATIVE_PLUGIN = '''
from .helpers import VALUE

from sophos.toolkit import FunctionTool


class P:
    name = "relative"
    version = "0.1.0"

    def setup(self, api):
        async def handler(params, context):
            return {"value": VALUE}

        api.register_tool(
            FunctionTool(
                name="relative_value",
                description="return helper value",
                handler=handler,
                parameters={"type": "object", "properties": {}},
            )
        )


PLUGIN = P()
'''


def _write_plugin(root: Path, name: str, source: str) -> Path:
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "plugin.py"
    path.write_text(source, encoding="utf-8")
    return path


class PluginManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.registry = ToolRegistry()
        self.state_store = MemoryPluginStateStore()

    async def asyncTearDown(self) -> None:
        self._tmp.cleanup()

    def make_manager(self) -> PluginManager:
        return PluginManager(
            registry=self.registry,
            plugin_dir=self.root,
            state_store=self.state_store,
        )

    async def test_directory_plugin_registers_tool_and_unregisters_on_close(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        manager = self.make_manager()
        await manager.init()

        self.assertIsNotNone(self.registry.get("demo_ping"))
        self.assertEqual(self.registry.origin_of("demo_ping"), plugin_origin("demo"))
        records = manager.list_plugins()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "loaded")
        self.assertEqual(records[0]["version"], "1.2.3")

        result = await self.registry.execute("demo_ping", {}, {})
        self.assertEqual(result, {"pong": "a"})

        await manager.close()
        self.assertIsNone(self.registry.get("demo_ping"))

    async def test_single_file_plugin_is_loaded(self) -> None:
        (self.root / "single.py").write_text(
            "from sophos.plugins import PluginMetadata\n"
            "class P:\n"
            "    metadata = PluginMetadata(name='single')\n"
            "    def setup(self, api):\n"
            "        @api.tool(name='single_tool', description='x')\n"
            "        async def tool(params, context):\n"
            "            return {'ok': True}\n"
            "PLUGIN = P()\n",
            encoding="utf-8",
        )
        manager = self.make_manager()
        await manager.init()
        try:
            self.assertIsNotNone(self.registry.get("single_tool"))
        finally:
            await manager.close()

    async def test_module_level_setup_is_supported(self) -> None:
        (self.root / "modular.py").write_text(
            "METADATA = {'name': 'modular', 'version': '2.0.0'}\n"
            "def setup(api):\n"
            "    @api.tool(name='modular_tool', description='x')\n"
            "    async def tool(params, context):\n"
            "        return 1\n",
            encoding="utf-8",
        )
        manager = self.make_manager()
        await manager.init()
        try:
            self.assertIsNotNone(self.registry.get("modular_tool"))
            self.assertEqual(manager.get("modular").metadata.version, "2.0.0")  # type: ignore[union-attr]
        finally:
            await manager.close()

    async def test_relative_imports_in_directory_plugin(self) -> None:
        plugin_dir = self.root / "relative"
        plugin_dir.mkdir()
        (plugin_dir / "helpers.py").write_text("VALUE = 42\n", encoding="utf-8")
        (plugin_dir / "plugin.py").write_text(_RELATIVE_PLUGIN, encoding="utf-8")
        manager = self.make_manager()
        await manager.init()
        try:
            result = await self.registry.execute("relative_value", {}, {})
            self.assertEqual(result, {"value": 42})
        finally:
            await manager.close()

    async def test_failed_plugin_reports_error_without_blocking_others(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        (self.root / "broken.py").write_text(
            "def setup(api):\n"
            "    raise RuntimeError('boom')\n",
            encoding="utf-8",
        )
        manager = self.make_manager()
        await manager.init()
        try:
            broken = manager.get("broken")
            self.assertIsNotNone(broken)
            self.assertEqual(broken.status, "failed")  # type: ignore[union-attr]
            self.assertIn("RuntimeError: boom", broken.error)  # type: ignore[union-attr]
            self.assertIsNotNone(self.registry.get("demo_ping"))
        finally:
            await manager.close()

    async def test_duplicate_plugin_name_is_rejected(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        (self.root / "demo_copy.py").write_text(
            "from sophos.plugins import PluginMetadata\n"
            "class P:\n"
            "    metadata = PluginMetadata(name='demo')\n"
            "    def setup(self, api):\n"
            "        @api.tool(name='copy_tool', description='x')\n"
            "        async def tool(params, context):\n"
            "            return 1\n"
            "PLUGIN = P()\n",
            encoding="utf-8",
        )
        manager = self.make_manager()
        await manager.init()
        try:
            self.assertIsNotNone(self.registry.get("demo_ping"))
            self.assertIsNone(self.registry.get("copy_tool"))
            records = {record["name"]: record for record in manager.list_plugins()}
            self.assertEqual(records["demo"]["status"], "loaded")
        finally:
            await manager.close()

    async def test_disable_then_enable_plugin(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        manager = self.make_manager()
        await manager.init()
        try:
            await manager.set_enabled("demo", False)
            self.assertIsNone(self.registry.get("demo_ping"))
            record = manager.get("demo")
            self.assertEqual(record.status, "disabled")  # type: ignore[union-attr]
            self.assertFalse(record.enabled)  # type: ignore[union-attr]
            stored = await self.state_store.load_all()
            self.assertFalse(stored["demo"].enabled)

            await manager.set_enabled("demo", True)
            self.assertIsNotNone(self.registry.get("demo_ping"))
            self.assertEqual(manager.get("demo").status, "loaded")  # type: ignore[union-attr]
        finally:
            await manager.close()

    async def test_config_merge_and_update_triggers_reload(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        manager = self.make_manager()
        await manager.init()
        try:
            record = manager.get("demo")
            self.assertEqual(record.config, {"prefix": "a"})  # type: ignore[union-attr]

            await manager.set_config("demo", {"prefix": "b"})
            result = await self.registry.execute("demo_ping", {}, {})
            self.assertEqual(result, {"pong": "b"})

            stored = await self.state_store.load_all()
            self.assertEqual(stored["demo"].config, {"prefix": "b"})
        finally:
            await manager.close()

    async def test_disabled_state_in_store_skips_setup(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        self.state_store.seed("demo", enabled=False)
        manager = self.make_manager()
        await manager.init()
        try:
            self.assertIsNone(self.registry.get("demo_ping"))
            self.assertEqual(manager.get("demo").status, "disabled")  # type: ignore[union-attr]
        finally:
            await manager.close()

    async def test_reload_plugin_keeps_tools_available(self) -> None:
        _write_plugin(self.root, "demo", _DEMO_PLUGIN)
        manager = self.make_manager()
        await manager.init()
        try:
            _write_plugin(self.root, "demo", _DEMO_PLUGIN.replace("demo_ping", "demo_ping_v2"))
            record = await manager.reload_plugin("demo")
            self.assertEqual(record.status, "loaded")
            self.assertIsNone(self.registry.get("demo_ping"))
            self.assertIsNotNone(self.registry.get("demo_ping_v2"))
        finally:
            await manager.close()


class RegistryOriginTests(unittest.IsolatedAsyncioTestCase):
    async def test_plugin_origin_cannot_remove_builtin_tool(self) -> None:
        from sophos.toolkit import FunctionTool

        registry = ToolRegistry()

        async def handler(params: dict[str, Any], context: dict[str, Any]) -> Any:
            return None

        tool = FunctionTool(name="shared", description="x", handler=handler)
        registry.register(tool)
        self.assertEqual(registry.origin_of("shared"), ORIGIN_BUILTIN)

        self.assertFalse(registry.unregister("shared", origin=plugin_origin("demo")))
        self.assertIsNotNone(registry.get("shared"))

        registry.register(tool, origin=plugin_origin("demo"))
        self.assertTrue(registry.unregister("shared", origin=plugin_origin("demo")))
        self.assertIsNone(registry.get("shared"))

    async def test_get_tools_info_exposes_origin_and_plugin(self) -> None:
        from sophos.toolkit import FunctionTool

        registry = ToolRegistry()

        async def handler(params: dict[str, Any], context: dict[str, Any]) -> Any:
            return None

        registry.register(
            FunctionTool(name="plugin_tool", description="x", handler=handler),
            origin=plugin_origin("demo"),
        )
        info = registry.get_tools_info()[0]
        self.assertEqual(info["origin"], "plugin:demo")
        self.assertEqual(info["plugin"], "demo")
        self.assertTrue(info["enabled"])


if __name__ == "__main__":
    unittest.main()
