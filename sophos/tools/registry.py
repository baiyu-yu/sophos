"""向后兼容层：工具注册中心已移动到 :mod:`sophos.toolkit.registry`。

新代码建议直接从 ``sophos.toolkit`` 导入。
"""

from sophos.toolkit.registry import (
    ORIGIN_BUILTIN,
    ORIGIN_PLUGIN_PREFIX,
    UNSAFE_DISABLE_TOOLS,
    ToolRegistry,
    origin_plugin_name,
    plugin_origin,
)

__all__ = [
    "ORIGIN_BUILTIN",
    "ORIGIN_PLUGIN_PREFIX",
    "UNSAFE_DISABLE_TOOLS",
    "ToolRegistry",
    "origin_plugin_name",
    "plugin_origin",
]
