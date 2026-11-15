"""工具子系统（Toolkit）。

独立于消息管线、数据库和 LLM 层的工具基座：

- :class:`Tool` / :class:`FunctionTool` — 工具抽象与函数式实现；
- :class:`ToolRegistry` — 注册、启用状态、执行与 schema 导出；
- 插件通过 :class:`sophos.plugins.api.PluginAPI` 向同一个注册表添加工具。

内置工具在 :mod:`sophos.tools`，插件在 :mod:`sophos.plugins`。
"""

from sophos.toolkit.base import FunctionTool, Tool, ToolHandler
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
    "FunctionTool",
    "Tool",
    "ToolHandler",
    "ToolRegistry",
    "origin_plugin_name",
    "plugin_origin",
]
