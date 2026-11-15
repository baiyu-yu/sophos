"""插件子系统：独立于内置工具的可扩展入口。

对外公开的对象：

- ``PluginManager`` — 插件发现/加载/卸载/热重载；
- ``PluginAPI`` — 传给插件 ``setup(api)`` 的能力入口；
- ``PluginMetadata`` — 插件元数据；
- ``PluginStateStore`` / ``DbPluginStateStore`` / ``MemoryPluginStateStore`` — 状态存储。

最小插件示例见 ``plugins/examples/demo/plugin.py``，完整文档见 ``docs/plugins.md``。
"""

from sophos.plugins.api import (
    PluginAPI,
    PluginHTTPError,
    PluginHTTPResponse,
    PluginRuntime,
)
from sophos.plugins.base import (
    PluginError,
    PluginInstallError,
    PluginLoadError,
    PluginMetadata,
    PluginNotFoundError,
)
from sophos.plugins.loader import LoadedPlugin, PluginManager
from sophos.plugins.state import (
    DbPluginStateStore,
    MemoryPluginStateStore,
    PluginState,
    PluginStateStore,
)

__all__ = [
    "DbPluginStateStore",
    "LoadedPlugin",
    "MemoryPluginStateStore",
    "PluginAPI",
    "PluginError",
    "PluginHTTPError",
    "PluginHTTPResponse",
    "PluginInstallError",
    "PluginLoadError",
    "PluginManager",
    "PluginMetadata",
    "PluginNotFoundError",
    "PluginRuntime",
    "PluginState",
    "PluginStateStore",
]
