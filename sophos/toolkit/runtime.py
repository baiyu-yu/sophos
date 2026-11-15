"""工具运行时单例与数据库状态缓存。

把「注册表实例 + 启用状态缓存」从消息管线中独立出来，插件管理器、API 路由、
消息管线都通过这里访问同一个 ToolRegistry。

依赖方向：本模块只依赖 ``sophos.toolkit``；对 ``sophos.tools`` / ``sophos.db``
的导入都放在函数内部，避免循环导入，也让 toolkit 本身可以被单独复用。
"""

from __future__ import annotations

import logging

from sophos.toolkit.registry import ToolRegistry

logger = logging.getLogger(__name__)

_registry: ToolRegistry | None = None
_disabled_loaded = False


def build_registry() -> ToolRegistry:
    """创建注册表并注册所有内置工具（不设置全局单例）。"""
    from sophos.tools import load_builtin_tools

    registry = ToolRegistry()
    for tool in load_builtin_tools():
        registry.register(tool)
    return registry


def get_registry() -> ToolRegistry:
    """获取或创建全局 ToolRegistry 单例。"""
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def peek_registry() -> ToolRegistry | None:
    """返回已创建的全局注册表；尚未创建时返回 None。"""
    return _registry


def set_registry(registry: ToolRegistry | None) -> None:
    """替换全局注册表（测试或自定义装配使用）。"""
    global _registry, _disabled_loaded
    _registry = registry
    _disabled_loaded = False


def reset_registry() -> None:
    """丢弃全局注册表，下次访问时重新创建（测试使用）。"""
    global _registry, _disabled_loaded
    _registry = None
    _disabled_loaded = False


async def load_disabled_state(registry: ToolRegistry | None = None) -> None:
    """从数据库加载工具禁用状态（每个进程只加载一次）。

    ``custom_tools.enabled = FALSE`` 的工具会被禁用；没有记录的工具保持注册表默认值。
    """
    global _disabled_loaded
    if _disabled_loaded:
        return
    from sophos.db import get_pool

    pool = get_pool()
    rows = await pool.fetch("SELECT name, enabled FROM custom_tools")
    target = registry if registry is not None else get_registry()
    for row in rows:
        if not row["enabled"]:
            target.set_disabled(row["name"], True)
    _disabled_loaded = True
    logger.debug("Loaded tool disabled state (%d rows)", len(rows))


def invalidate_disabled_state() -> None:
    """清除禁用状态缓存，下次调用时重新从数据库加载。"""
    global _disabled_loaded
    _disabled_loaded = False
    if _registry is not None:
        _registry.clear_disabled()
