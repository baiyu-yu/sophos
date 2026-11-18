"""ToolRegistry — 工具的注册中心（与具体应用解耦）。

工具来源（origin）用于区分内置工具与插件工具：
- ``"builtin"`` — 随 Sophos 分发的内置工具；
- ``"plugin:<name>"`` — 由某个插件注册的工具。

WebUI 用来源标记展示「内置 / 插件」并决定默认启用状态。
"""

from __future__ import annotations

import logging
from typing import Any

from sophos.llm.schema import strip_boundary_nulls
from sophos.toolkit.base import Tool

logger = logging.getLogger(__name__)

UNSAFE_DISABLE_TOOLS: frozenset[str] = frozenset({"send_message"})

ORIGIN_BUILTIN = "builtin"
ORIGIN_PLUGIN_PREFIX = "plugin:"


def plugin_origin(plugin_name: str) -> str:
    """把插件名转换成注册来源标记。"""
    return f"{ORIGIN_PLUGIN_PREFIX}{plugin_name}"


def _is_blank(value: Any) -> bool:
    """必填参数缺失判定：None、空白字符串都算缺失。"""
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def origin_plugin_name(origin: str) -> str | None:
    """从来源标记中取出插件名；内置工具返回 None。"""
    if origin.startswith(ORIGIN_PLUGIN_PREFIX):
        return origin[len(ORIGIN_PLUGIN_PREFIX) :]
    return None


class ToolRegistry:
    """管理所有已注册的工具。

    用法:
        registry = ToolRegistry()
        registry.register(SendMessageTool())
        registry.register(WebSearchTool(), origin=plugin_origin("my-plugin"))

        # 代码直接调用
        result = await registry.execute("send_message", params, context)

        # 导出给 LLM
        schemas = registry.get_function_schemas()
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._origins: dict[str, str] = {}
        self._disabled_tools: set[str] = set()

    def register(self, tool: Tool, *, origin: str = ORIGIN_BUILTIN) -> None:
        """注册一个工具。重名会覆盖并警告（插件可以覆盖内置工具，风险自负）。"""
        if tool.name in self._tools:
            logger.warning("Tool '%s' is being overridden (origin=%s)", tool.name, origin)
        self._tools[tool.name] = tool
        self._origins[tool.name] = origin
        logger.debug("Registered tool: %s (origin=%s)", tool.name, origin)

    def unregister(self, name: str, *, origin: str | None = None) -> bool:
        """移除一个工具。

        Args:
            name: 工具名。
            origin: 若提供，只有当工具来源匹配时才移除（防止插件误删内置工具）。

        Returns:
            是否真的移除了工具。
        """
        if name not in self._tools:
            return False
        if origin is not None and self._origins.get(name) != origin:
            return False
        self._tools.pop(name, None)
        self._origins.pop(name, None)
        self._disabled_tools.discard(name)
        logger.debug("Unregistered tool: %s", name)
        return True

    def unregister_origin(self, origin: str) -> list[str]:
        """移除某个来源注册的全部工具，返回被移除的工具名。"""
        names = [name for name, tool_origin in self._origins.items() if tool_origin == origin]
        for name in names:
            self.unregister(name, origin=origin)
        return names

    def get(self, name: str) -> Tool | None:
        """按名称查找工具。"""
        return self._tools.get(name)

    def origin_of(self, name: str) -> str | None:
        """返回工具来源标记。"""
        return self._origins.get(name)

    def list_tools(self) -> list[str]:
        """列出所有已注册工具的名称。"""
        return list(self._tools.keys())

    def set_disabled(self, name: str, disabled: bool) -> bool:
        """设置工具禁用状态。返回是否成功（send_message 不可禁用）。"""
        if disabled and name in UNSAFE_DISABLE_TOOLS:
            return False
        if disabled:
            self._disabled_tools.add(name)
        else:
            self._disabled_tools.discard(name)
        return True

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled_tools

    def clear_disabled(self) -> None:
        """清除所有禁用状态（用于从数据库重新加载）。"""
        self._disabled_tools.clear()

    async def execute(
        self,
        name: str,
        params: dict[str, Any],
        context: dict[str, Any],
        *,
        allowed_tools: set[str] | None = None,
    ) -> Any:
        """按名称调用工具。

        这是代码直接调用工具的入口，也是 LLM tool calling 的执行入口。
        调用前自动校验 required 参数是否齐全。
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        if name in self._disabled_tools:
            raise PermissionError(f"Tool is disabled: {name}")
        if allowed_tools is not None and name not in allowed_tools:
            raise PermissionError(f"Tool is not allowed in this context: {name}")
        capabilities = set(context.get("adapter_capabilities", ()))
        if not tool.required_capabilities.issubset(capabilities):
            missing = sorted(tool.required_capabilities - capabilities)
            raise PermissionError(f"Adapter capability unavailable for {name}: {', '.join(missing)}")
        conversation_kind = context.get("conversation_kind")
        if tool.conversation_kinds is not None and conversation_kind not in tool.conversation_kinds:
            raise PermissionError(
                f"Tool {name} is unavailable in conversation kind: {conversation_kind or 'unknown'}"
            )

        # 轻量参数校验：检查 required 字段是否齐全（null/空白也算缺失）
        schema = tool.parameters
        required = schema.get("required", [])
        missing = [key for key in required if _is_blank(params.get(key))]
        if missing:
            hint = tool.missing_required_hint.strip()
            message = f"缺少必填参数: {', '.join(missing)}"
            if hint:
                message = f"{message}。{hint}"
            return {"error": message}

        params = strip_boundary_nulls(params, schema)
        return await tool.execute(params, context)

    def get_function_schemas(
        self,
        *,
        category: str | None = None,
        conversation_kind: str | None = None,
        description_overrides: dict[str, str] | None = None,
        capabilities: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """导出工具的 schema，用于传给 LLM 的 tools 字段。

        Args:
            category: 按类别过滤，"input" 或 "output"。None 表示全部。
            conversation_kind: 按通用会话类型过滤（direct/group/channel/thread）。
            description_overrides: 工具描述覆盖 {tool_name: custom_description}。
            capabilities: 只导出能力要求被满足的工具。
        """
        tools: list[Tool] = [t for t in self._tools.values() if t.name not in self._disabled_tools]
        if category is not None:
            tools = [t for t in tools if t.category == category]
        if conversation_kind is not None:
            tools = [
                tool
                for tool in tools
                if tool.conversation_kinds is None or conversation_kind in tool.conversation_kinds
            ]
        if capabilities is not None:
            tools = [t for t in tools if t.required_capabilities.issubset(capabilities)]

        schemas = []
        for tool in tools:
            schema = tool.to_function_schema()
            if description_overrides and tool.name in description_overrides:
                schema = {
                    **schema,
                    "function": {
                        **schema["function"],
                        "description": description_overrides[tool.name],
                    },
                }
            schemas.append(schema)
        return schemas

    def get_tools_info(self, *, description_overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """导出所有工具的元信息，供 WebUI 展示。

        Args:
            description_overrides: 从 DB 加载的描述覆盖 {tool_name: custom_description}。

        Returns:
            工具信息列表，每个元素包含：
            name, description, default_description, has_custom_description, category,
            conversation_kinds, group, is_builtin, is_custom, origin, plugin,
            enabled, parameters, can_disable
        """
        result = []
        for tool in self._tools.values():
            default_desc = tool.description
            custom_desc = description_overrides.get(tool.name) if description_overrides else None
            effective_desc = custom_desc if custom_desc else default_desc
            origin = self._origins.get(tool.name, ORIGIN_BUILTIN)

            result.append(
                {
                    "name": tool.name,
                    "description": effective_desc,
                    "default_description": default_desc,
                    "has_custom_description": custom_desc is not None,
                    "category": tool.category,
                    "conversation_kinds": (
                        sorted(tool.conversation_kinds) if tool.conversation_kinds is not None else None
                    ),
                    "group": tool.group,
                    "is_builtin": tool.is_builtin,
                    "is_custom": not tool.is_builtin,
                    "origin": origin,
                    "plugin": origin_plugin_name(origin),
                    "enabled": tool.name not in self._disabled_tools,
                    "parameters": tool.parameters,
                    "can_disable": tool.name not in UNSAFE_DISABLE_TOOLS,
                }
            )
        return result
