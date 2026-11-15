"""插件发现、加载、卸载与热重载。

插件来源（按优先级）：

1. ``<PLUGINS_DIR>/<name>/plugin.py`` — 目录插件，按包加载，支持相对导入
   同目录的辅助模块（``from .helpers import ...``）；
2. ``<PLUGINS_DIR>/<name>.py`` — 单文件插件；
3. Python entry point ``sophos.plugins`` — 适合以 pip 包形式分发的插件。

插件模块需要满足以下任一形式：

- 模块级 ``setup(api)``（可选 ``teardown()``、``METADATA`` 字典）；
- 模块级 ``PLUGIN`` 对象或类，带 ``setup(api)`` / ``teardown()`` 与元数据属性。

加载失败不会影响 Sophos 启动：失败的插件会出现在管理接口里，附带错误信息。
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import inspect
import logging
import re
import sys
import types
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import aiohttp

from sophos.config import settings
from sophos.plugins.api import PluginAPI, PluginRuntime
from sophos.plugins.base import (
    PluginError,
    PluginInstallError,
    PluginLoadError,
    PluginMetadata,
    PluginNotFoundError,
)
from sophos.plugins.install import install_file as _install_file
from sophos.plugins.install import install_zip as _install_zip
from sophos.plugins.install import remove_installed as _remove_installed
from sophos.plugins.state import PluginState, PluginStateStore
from sophos.toolkit.registry import ToolRegistry, plugin_origin

logger = logging.getLogger(__name__)

MODULE_PREFIX = "sophos_plugins"
_ENTRY_POINT_GROUP = "sophos.plugins"
_PLUGIN_FILE = "plugin.py"
_MAX_HTTP_TIMEOUT = 60.0


@dataclass(slots=True)
class DiscoveredPlugin:
    """发现阶段得到的一个插件候选。"""

    name: str
    path: Path | None = None
    source: str = "directory"  # directory | file | entry_point
    entry_point: str | None = None
    module_name: str | None = None


@dataclass(slots=True)
class LoadedPlugin:
    """一个已经导入（可能已启用）的插件。"""

    metadata: PluginMetadata
    discovered: DiscoveredPlugin
    enabled: bool = True
    status: str = "loaded"  # loaded | disabled | failed
    error: str | None = None
    started: bool = False
    tools: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    module: ModuleType | None = None
    api: PluginAPI | None = None
    teardown: Callable[..., Any] | None = None

    @property
    def name(self) -> str:
        return self.metadata.name


class PluginManager:
    """插件生命周期管理器。"""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        plugin_dir: str | Path | None = None,
        state_store: PluginStateStore | None = None,
        adapter_router: Any | None = None,
        message_service: Any | None = None,
        store: Any | None = None,
        pool: Any | None = None,
        provider_mgr: Any | None = None,
        memory_store: Any | None = None,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._plugin_dir = Path(plugin_dir if plugin_dir is not None else settings.plugins_dir)
        self._state_store = state_store
        self._runtime = PluginRuntime(
            registry=registry,
            adapter_router=adapter_router,
            message_service=message_service,
            store=store,
            pool=pool,
            provider_mgr=provider_mgr,
            memory_store=memory_store,
            http=http_session,
        )
        self._http = http_session
        self._owns_http = False
        self._plugins: dict[str, LoadedPlugin] = {}
        self._states: dict[str, PluginState] = {}
        self._lock = asyncio.Lock()

    # ---- 只读属性 -------------------------------------------------------

    @property
    def plugins_dir(self) -> Path:
        return self._plugin_dir

    @property
    def runtime(self) -> PluginRuntime:
        return self._runtime

    def get(self, name: str) -> LoadedPlugin | None:
        return self._plugins.get(name)

    # ---- 生命周期 -------------------------------------------------------

    async def init(self) -> None:
        """创建 HTTP 会话、载入持久化状态并加载所有插件。"""
        async with self._lock:
            if self._http is None:
                self._http = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=_MAX_HTTP_TIMEOUT)
                )
                self._owns_http = True
                self._runtime.http = self._http
            await self._load_states()
            await self._load_all()

    async def reload(self, name: str | None = None) -> LoadedPlugin | None:
        """重新发现并加载插件；传 ``name`` 时只重载该插件。"""
        async with self._lock:
            await self._load_states()
            if name is not None:
                return await self._reload_one(name)
            await self._unload_all()
            self._plugins.clear()
            await self._load_all()
            return None

    async def reload_plugin(self, name: str) -> LoadedPlugin:
        async with self._lock:
            await self._load_states()
            return await self._reload_one(name)

    async def set_enabled(self, name: str, enabled: bool) -> LoadedPlugin:
        """启用/停用插件，并立即生效、写入持久化状态。"""
        async with self._lock:
            record = self._plugins.get(name)
            if record is None:
                raise PluginNotFoundError(name)
            if self._state_store is not None:
                await self._state_store.set_enabled(name, enabled)
            self._states[name] = PluginState(enabled=enabled, config=dict(record.config))
            if not enabled:
                await self._stop_plugin(record)
                record.enabled = False
                record.status = "disabled"
                return record
            return await self._restart(record, enabled=True, config=record.config)

    async def set_config(self, name: str, config: Mapping[str, Any]) -> LoadedPlugin:
        """覆盖插件配置；插件处于启用状态时会自动重载以应用新配置。"""
        async with self._lock:
            record = self._plugins.get(name)
            if record is None:
                raise PluginNotFoundError(name)
            merged = {**dict(record.metadata.default_config), **dict(config)}
            if self._state_store is not None:
                await self._state_store.set_config(name, dict(config))
            self._states[name] = PluginState(enabled=record.enabled, config=merged)
            if not record.enabled:
                record.config = merged
                return record
            return await self._restart(record, enabled=True, config=merged)

    async def install_zip(
        self,
        filename: str,
        data: bytes,
        *,
        overwrite: bool = False,
    ) -> LoadedPlugin:
        """从上传的 zip 安装目录插件并立即加载。"""
        async with self._lock:
            name = _install_zip(self._plugin_dir, filename, data, overwrite=overwrite)
            return await self._reload_after_install(name)

    async def install_file(
        self,
        filename: str,
        data: bytes,
        *,
        overwrite: bool = False,
    ) -> LoadedPlugin:
        """从上传的单个 ``.py`` 安装插件并立即加载。"""
        async with self._lock:
            name = _install_file(self._plugin_dir, filename, data, overwrite=overwrite)
            return await self._reload_after_install(name)

    async def uninstall(self, name: str) -> None:
        """停用并删除插件文件，同时清理持久化的开关与配置。"""
        async with self._lock:
            record = self._plugins.get(name)
            item = record.discovered if record is not None else self._discover().get(name)
            if item is None or item.path is None:
                raise PluginNotFoundError(name)
            if item.source == "entry_point":
                raise PluginInstallError("entry point 安装的插件不能通过 WebUI 删除")
            if record is not None:
                await self._stop_plugin(record)
            _remove_installed(self._plugin_dir, name, item.path, source=item.source)
            self._plugins.pop(name, None)
            self._states.pop(name, None)
            if self._state_store is not None:
                await self._state_store.delete(name)

    async def _reload_after_install(self, name: str) -> LoadedPlugin:
        await self._load_states()
        item = self._discover().get(name)
        if item is None:
            raise PluginInstallError(f"安装后未能发现插件 {name}")
        stale: list[LoadedPlugin] = []
        old = self._plugins.get(name)
        if old is not None:
            stale.append(old)
        for key, existing in list(self._plugins.items()):
            if existing is not old and existing.discovered.path == item.path:
                stale.append(existing)
                self._plugins.pop(key, None)
        for existing in stale:
            for key, value in list(self._plugins.items()):
                if value is existing:
                    self._plugins.pop(key, None)
            await self._stop_plugin(existing)
        record = await self._load_plugin(item)
        self._plugins[record.name] = record
        return record

    async def close(self) -> None:
        """卸载全部插件并释放自己创建的 HTTP 会话。"""
        async with self._lock:
            await self._unload_all()
            self._plugins.clear()
            if self._owns_http and self._http is not None:
                await self._http.close()
                self._http = None
                self._runtime.http = None

    # ---- 展示 -----------------------------------------------------------

    def list_plugins(self) -> list[dict[str, Any]]:
        """返回供管理接口/WebUI 使用的插件列表。"""
        return [self.describe(record) for record in sorted(self._plugins.values(), key=lambda item: item.name)]

    def describe(self, record: LoadedPlugin) -> dict[str, Any]:
        """把单个插件记录序列化成 API/WebUI 使用的字典。"""
        return {
            "name": record.name,
            "version": record.metadata.version,
            "description": record.metadata.description,
            "author": record.metadata.author,
            "homepage": record.metadata.homepage,
            "enabled": record.enabled,
            "status": record.status,
            "error": record.error,
            "tools": list(record.tools),
            "config": dict(record.config),
            "default_config": dict(record.metadata.default_config),
            "path": str(record.discovered.path) if record.discovered.path else None,
            "source": record.discovered.source,
        }

    # ---- 内部：状态与发现 ----------------------------------------------

    async def _load_states(self) -> None:
        if self._state_store is None:
            return
        try:
            self._states = await self._state_store.load_all()
        except Exception:
            logger.exception("读取插件状态失败，按默认值继续")
            self._states = {}

    def _state_for(self, *names: str) -> PluginState:
        for candidate in names:
            state = self._states.get(candidate)
            if state is not None:
                return state
        return PluginState()

    def _discover(self) -> dict[str, DiscoveredPlugin]:
        found: dict[str, DiscoveredPlugin] = {}
        if self._plugin_dir.is_dir():
            for entry in sorted(self._plugin_dir.iterdir()):
                if entry.name.startswith((".", "_")):
                    continue
                if entry.is_dir() and (entry / _PLUGIN_FILE).is_file():
                    found[entry.name] = DiscoveredPlugin(
                        name=entry.name, path=entry / _PLUGIN_FILE, source="directory"
                    )
                elif entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
                    found[entry.stem] = DiscoveredPlugin(name=entry.stem, path=entry, source="file")
        for entry_point in _entry_points():
            if entry_point.name in found:
                logger.warning("插件 %s 同时由目录和 entry point 提供，忽略 entry point", entry_point.name)
                continue
            found[entry_point.name] = DiscoveredPlugin(
                name=entry_point.name, source="entry_point", entry_point=entry_point.value
            )
        return found

    async def _load_all(self) -> None:
        for item in self._discover().values():
            record = await self._load_plugin(item)
            self._plugins[record.name] = record

    async def _reload_one(self, name: str) -> LoadedPlugin:
        discovered = self._discover()
        old = self._plugins.pop(name, None)
        item = discovered.get(name) or (old.discovered if old is not None else None)
        if item is None:
            raise PluginNotFoundError(name)
        if old is not None:
            await self._stop_plugin(old)
        record = await self._load_plugin(item)
        self._plugins[record.name] = record
        return record

    async def _restart(self, record: LoadedPlugin, *, enabled: bool, config: dict[str, Any]) -> LoadedPlugin:
        await self._stop_plugin(record)
        self._plugins.pop(record.name, None)
        fresh = await self._load_plugin(record.discovered, enabled=enabled, config_stored=config)
        self._plugins[fresh.name] = fresh
        return fresh

    async def _unload_all(self) -> None:
        for record in list(self._plugins.values()):
            await self._stop_plugin(record)

    # ---- 内部：导入与初始化 --------------------------------------------

    async def _load_plugin(
        self,
        item: DiscoveredPlugin,
        *,
        enabled: bool | None = None,
        config_stored: dict[str, Any] | None = None,
    ) -> LoadedPlugin:
        record = LoadedPlugin(metadata=PluginMetadata(name=item.name), discovered=item)
        try:
            module = self._import_module(item)
            definition = _extract_definition(module, item.name)
            plugin_name = definition.metadata.name
            if plugin_name in self._plugins and self._plugins[plugin_name].discovered is not item:
                raise PluginLoadError(f"插件名冲突: {plugin_name}")

            state = self._state_for(plugin_name, item.name)
            is_enabled = state.enabled if enabled is None else enabled
            stored = dict(state.config) if config_stored is None else dict(config_stored)
            config = {**dict(definition.metadata.default_config), **stored}

            api = PluginAPI(metadata=definition.metadata, runtime=self._runtime, config=config)
            record.metadata = definition.metadata
            record.config = config
            record.enabled = is_enabled
            record.module = module
            record.api = api
            record.teardown = definition.teardown

            if is_enabled:
                # 先标记为已启动：setup 中途失败时也要执行卸载回调与 teardown。
                record.started = True
                await _call_maybe_async(definition.setup, api)
                record.tools = list(api.tools)
                record.status = "loaded"
                logger.info(
                    "已加载插件 %s v%s（%d 个工具）",
                    plugin_name,
                    definition.metadata.version,
                    len(record.tools),
                )
            else:
                record.status = "disabled"
                logger.info("插件 %s 已发现但处于停用状态", plugin_name)
            return record
        except Exception as exc:
            logger.exception("加载插件 %s 失败", item.name)
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            # 失败记录不要占用同名已成功插件的 key，否则会把它覆盖掉。
            if record.metadata.name in self._plugins and self._plugins[record.metadata.name].discovered is not item:
                record.metadata = PluginMetadata(name=item.name)
            await self._stop_plugin(record)
            return record

    def _import_module(self, item: DiscoveredPlugin) -> ModuleType:
        if item.source == "entry_point":
            return _load_entry_point(item)
        if item.path is None:
            raise PluginLoadError(f"插件 {item.name} 缺少文件路径")
        module_name = f"{MODULE_PREFIX}.{_sanitize_identifier(item.name)}"
        _remove_module(module_name)
        package_locations = [str(item.path.parent)] if item.source == "directory" else None
        if package_locations is not None:
            _ensure_parent_package(self._plugin_dir)
        spec = importlib.util.spec_from_file_location(
            module_name, str(item.path), submodule_search_locations=package_locations
        )
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"无法为插件 {item.name} 创建模块规格: {item.path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            _remove_module(module_name)
            raise
        item.module_name = module_name
        return module

    async def _stop_plugin(self, record: LoadedPlugin) -> None:
        if record.started:
            if record.api is not None:
                await record.api.run_unload_handlers()
            if record.teardown is not None:
                try:
                    await _call_maybe_async(record.teardown)
                except Exception:
                    logger.exception("插件 %s 的 teardown 失败", record.name)
            record.started = False
        self._runtime.registry.unregister_origin(plugin_origin(record.name))
        if record.discovered.module_name:
            _remove_module(record.discovered.module_name)
        record.tools = []
        record.api = None
        record.module = None


@dataclass(slots=True)
class _PluginDefinition:
    metadata: PluginMetadata
    setup: Callable[..., Any]
    teardown: Callable[..., Any] | None = None


def _extract_definition(module: ModuleType, fallback_name: str) -> _PluginDefinition:
    plugin_object = getattr(module, "PLUGIN", None)
    metadata_fields: dict[str, Any] = {}
    raw_metadata = getattr(module, "METADATA", None)
    if isinstance(raw_metadata, Mapping):
        metadata_fields.update(raw_metadata)

    if isinstance(plugin_object, type):
        plugin_object = plugin_object()

    if plugin_object is not None:
        # PLUGIN.metadata 可以是 PluginMetadata，也可以是普通 dict。
        declared = getattr(plugin_object, "metadata", None)
        if isinstance(declared, PluginMetadata):
            metadata_fields.update(
                {
                    "name": declared.name,
                    "version": declared.version,
                    "description": declared.description,
                    "author": declared.author,
                    "homepage": declared.homepage,
                    "default_config": declared.default_config,
                }
            )
        elif isinstance(declared, Mapping):
            metadata_fields.update(declared)
        for attribute in ("name", "version", "description", "author", "homepage"):
            value = getattr(plugin_object, attribute, None)
            if value is not None:
                metadata_fields[attribute] = value
        default_config = getattr(plugin_object, "default_config", None)
        setup = getattr(plugin_object, "setup", None)
        teardown = getattr(plugin_object, "teardown", None)
        if default_config is None:
            default_config = metadata_fields.get("default_config")
    else:
        setup = getattr(module, "setup", None)
        teardown = getattr(module, "teardown", None)
        default_config = metadata_fields.get("default_config")

    if not callable(setup):
        raise PluginLoadError(
            f"插件 {fallback_name} 需要定义 PLUGIN 对象（含 setup）或模块级 setup(api) 函数"
        )

    metadata = PluginMetadata(
        name=str(metadata_fields.get("name") or fallback_name),
        version=str(metadata_fields.get("version") or "0.1.0"),
        description=str(metadata_fields.get("description") or ""),
        author=str(metadata_fields.get("author") or ""),
        homepage=str(metadata_fields.get("homepage") or ""),
        default_config=dict(default_config) if isinstance(default_config, Mapping) else {},
    )
    return _PluginDefinition(
        metadata=metadata,
        setup=setup,
        teardown=teardown if callable(teardown) else None,
    )


async def _call_maybe_async(function: Callable[..., Any], *args: Any) -> Any:
    result = function(*args)
    if inspect.isawaitable(result):
        return await result
    return result


def _entry_points() -> list[importlib.metadata.EntryPoint]:
    try:
        return list(importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP))
    except TypeError:  # pragma: no cover - 老版本 Python 的兼容路径
        entry_points = importlib.metadata.entry_points()
        return list(entry_points.get(_ENTRY_POINT_GROUP, []))


def _load_entry_point(item: DiscoveredPlugin) -> ModuleType:
    for entry_point in _entry_points():
        if entry_point.name != item.name:
            continue
        loaded = entry_point.load()
        if isinstance(loaded, ModuleType):
            return loaded
        wrapper = types.ModuleType(f"{MODULE_PREFIX}.{_sanitize_identifier(item.name)}")
        wrapper.PLUGIN = loaded
        item.module_name = wrapper.__name__
        sys.modules[wrapper.__name__] = wrapper
        return wrapper
    raise PluginLoadError(f"找不到 entry point: {item.name}")


def _sanitize_identifier(value: str) -> str:
    sanitized = re.sub(r"[^0-9A-Za-z_]", "_", value)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"p_{sanitized}"
    return sanitized


def _ensure_parent_package(plugin_dir: Path) -> None:
    """把 ``sophos_plugins`` 注册成包，保证目录插件的相对导入可用。"""
    if MODULE_PREFIX in sys.modules:
        return
    parent = types.ModuleType(MODULE_PREFIX)
    parent.__path__ = [str(plugin_dir)]  # type: ignore[attr-defined]
    parent.__package__ = MODULE_PREFIX
    sys.modules[MODULE_PREFIX] = parent


def _remove_module(module_name: str) -> None:
    for key in [key for key in sys.modules if key == module_name or key.startswith(f"{module_name}.")]:
        sys.modules.pop(key, None)


__all__ = [
    "DiscoveredPlugin",
    "LoadedPlugin",
    "PluginError",
    "PluginLoadError",
    "PluginManager",
    "PluginNotFoundError",
]
