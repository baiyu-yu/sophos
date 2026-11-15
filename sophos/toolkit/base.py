"""Tool 抽象基类与函数式工具 — 工具子系统的独立基座。

这个模块只依赖标准库：任何插件、内置工具或第三方代码都可以直接复用，
不需要导入 Sophos 的数据库、消息管线或 LLM 层。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

ToolHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]]


class Tool(ABC):
    """一个可被 LLM 或代码调用的工具。

    每个 Tool 子类需要定义：
    - name:        工具名（唯一标识，LLM 用这个名字来调用）
    - description: 一句话描述（给 LLM 看的，帮它决定什么时候用这个工具）
    - parameters:  参数的 JSON Schema（告诉 LLM 要传什么参数、什么类型）
    - execute():   实际执行逻辑

    可选覆盖：
    - category:    工具类别，"input"（查询）或 "output"（操作），默认 "input"
    - conversation_kinds: 适用的通用会话类型；None 表示全部
    - group:       工具分组，用于 WebUI 展示分类，默认 "other"
    - required_capabilities: 执行前需要的平台能力（如 message.send）
    - is_builtin:  是否内置工具；插件注册的工具由 ToolRegistry 的来源标记决定
    """

    @property
    def category(self) -> str:
        return "input"

    @property
    def conversation_kinds(self) -> frozenset[str] | None:
        return None

    @property
    def group(self) -> str:
        """工具分组：WebUI 按此字段归类展示。

        内置工具返回具体分组名，如 "messaging"、"memory"；插件可自定义分组，
        建议使用 "plugin" 或 "plugin:<插件名>" 以便在 WebUI 中归类。
        """
        return "other"

    @property
    def required_capabilities(self) -> frozenset[str]:
        """Adapter capabilities required to expose and execute this tool."""
        return frozenset()

    @property
    def is_builtin(self) -> bool:
        """是否为内置工具（不可删除）。插件工具通常返回 False。"""
        return True

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名，如 "send_message"。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，给 LLM 看的。"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """参数的 JSON Schema。

        例:
            {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "integer", "description": "Sophos 内部会话 ID"},
                    "message":  {"type": "string",  "description": "消息内容"},
                },
                "required": ["message"],
            }
        """
        ...

    @abstractmethod
    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行工具。

        Args:
            params:  调用参数（已通过 JSON Schema 校验）
            context: 平台中立的运行时上下文，由调用方注入

        Returns:
            工具执行结果，会被序列化后返回给 LLM 或调用方。
        """
        ...

    def to_function_schema(self) -> dict[str, Any]:
        """导出为 LLM function calling 的 schema。

        输出格式兼容 OpenAI API 的 tools 字段，
        同时也兼容大多数中转服务和本地部署方案。
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class FunctionTool(Tool):
    """用一个 async 函数快速定义工具。

    插件里最常用的写法::

        tool = FunctionTool(
            name="echo",
            description="原样返回输入",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}},
            handler=lambda params, context: _echo(params),
        )

    也可以直接使用 ``PluginAPI.tool()`` 装饰器，它内部就是构造 FunctionTool。
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        handler: ToolHandler,
        parameters: dict[str, Any] | None = None,
        category: str = "input",
        group: str = "plugin",
        conversation_kinds: frozenset[str] | None = None,
        required_capabilities: frozenset[str] = frozenset(),
        is_builtin: bool = False,
    ) -> None:
        if not name:
            raise ValueError("FunctionTool requires a non-empty name")
        self._name = name
        self._description = description
        self._handler = handler
        self._parameters = parameters or {"type": "object", "properties": {}}
        self._category = category
        self._group = group
        self._conversation_kinds = conversation_kinds
        self._required_capabilities = frozenset(required_capabilities)
        self._is_builtin = is_builtin

    @property
    def category(self) -> str:
        return self._category

    @property
    def conversation_kinds(self) -> frozenset[str] | None:
        return self._conversation_kinds

    @property
    def group(self) -> str:
        return self._group

    @property
    def required_capabilities(self) -> frozenset[str]:
        return self._required_capabilities

    @property
    def is_builtin(self) -> bool:
        return self._is_builtin

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        return await self._handler(params, context)
