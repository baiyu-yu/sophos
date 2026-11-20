"""插件 API — 插件能够使用的全部能力都收敛在这里。

设计目标：插件作者只需要读这一个文件（和 ``docs/plugins.md``）就能知道
自己能做什么，而不必了解 Sophos 内部的消息管线、数据库表结构或适配器实现。

四大能力：

1. **工具**：``api.tool()`` / ``api.register_tool()`` 注册任意工具；
2. **内置能力**：``api.call_tool()`` 调用已注册的任何工具（内置或其它插件的）；
3. **消息**：``api.send_message()`` 通过平台中立的 MessageService 发消息；
4. **协议端直连**：``api.protocol.call()`` 直接把 action 发给 OneBot 等协议端；
   另外 ``api.http`` 用于访问外部 HTTP API，``api.db`` 提供受限的数据库访问，
   ``api.logger`` 是带插件名前缀的 logger。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import aiohttp

from sophos import runtime_config
from sophos.config import settings
from sophos.platform import SendMessageRequest
from sophos.toolkit.base import FunctionTool, Tool, ToolHandler
from sophos.toolkit.registry import plugin_origin

if TYPE_CHECKING:
    from sophos.adapter_router import AdapterRouter
    from sophos.messaging import MessageService
    from sophos.toolkit.registry import ToolRegistry

PluginUnloadHandler = Callable[[], Awaitable[None] | None]

_DEFAULT_HTTP_TIMEOUT = 30.0
_MAX_HTTP_BYTES = 10 * 1024 * 1024


@dataclass(slots=True)
class PluginRuntime:
    """插件运行所依赖的宿主对象集合。

    由 PluginManager 在启动时构造并注入；插件本身不直接接触这些对象，
    而是通过 PluginAPI 暴露的稳定接口使用它们。
    """

    registry: ToolRegistry
    adapter_router: AdapterRouter | None = None
    message_service: MessageService | None = None
    store: Any | None = None
    pool: Any | None = None
    provider_mgr: Any | None = None
    memory_store: Any | None = None
    http: aiohttp.ClientSession | None = None

    def adapter_capabilities(self) -> set[str]:
        """返回当前所有在线适配器能力的并集。"""
        capabilities: set[str] = set()
        if self.adapter_router is None:
            return capabilities
        for adapter in self.adapter_router.adapters():
            capabilities.update(capability.value for capability in adapter.capabilities)
        return capabilities

    def default_tool_context(self) -> dict[str, Any]:
        """构造一个「不绑定具体会话」的工具上下文。

        插件在自己的定时任务、Webhook 回调里调用 ``api.call_tool()`` 时，
        如果没有会话上下文，就会使用这份默认上下文。依赖会话的工具
        （如 ``send_message``）仍需要显式传入 ``conversation_id``。
        """
        context: dict[str, Any] = {
            "message_service": self.message_service,
            "store": self.store,
            "pool": self.pool,
            "provider_mgr": self.provider_mgr,
            "adapter_capabilities": self.adapter_capabilities(),
            "timezone": str(runtime_config.get("timezone") or settings.timezone),
        }
        if self.message_service is not None:
            context["platform_store"] = self.message_service.platform_store
        if self.memory_store is not None:
            context["memory_store"] = self.memory_store
            if self.provider_mgr is not None:
                context["embedding_provider"] = self.provider_mgr.get_embedding_provider()
        if self.provider_mgr is not None:
            vision_provider = self.provider_mgr.get_vision_provider()
            if vision_provider:
                context["vision_provider"] = vision_provider
        return context


@dataclass(frozen=True, slots=True)
class PluginHTTPResponse:
    """``api.http`` 的响应对象。"""

    status: int
    headers: Mapping[str, str]
    content: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class PluginHTTPError(RuntimeError):
    """HTTP 请求失败或响应体超过大小限制。"""


class PluginProtocolAPI:
    """协议端直连接口：把 action 原样发送给已连接的协议实现。"""

    def __init__(self, runtime: PluginRuntime) -> None:
        self._runtime = runtime

    def accounts(self) -> list[int]:
        """返回当前已连接的账号 ID 列表。"""
        if self._runtime.adapter_router is None:
            return []
        return self._runtime.adapter_router.connected_accounts()

    async def call(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        account_id: int | None = None,
        timeout: float | None = None,
    ) -> Any:
        """直接调用协议端接口（OneBot 11 的 action）。

        Example:
            ``await api.protocol.call("get_group_info", {"group_id": 123456})``

        Args:
            action: 协议 action 名，例如 ``send_msg`` / ``get_group_list``。
            params: action 参数，原样透传。
            account_id: 指定账号；``None`` 时使用第一个在线适配器。
            timeout: 超时秒数；``None`` 使用协议实现的默认值。

        Raises:
            RuntimeError: 没有已连接的适配器，或适配器不支持协议直连。
        """
        router = self._runtime.adapter_router
        if router is None:
            raise RuntimeError("插件 API 未接入适配器路由，无法直连协议端")
        try:
            adapter = router.raw_adapter(account_id)
        except Exception as exc:  # noqa: BLE001 - 统一转换成插件可读的错误
            raise RuntimeError(f"无法连接协议端: {exc}") from exc
        return await adapter.call_protocol_api(action, params, timeout=timeout)


class PluginHTTPAPI:
    """给插件用的轻量 HTTP 客户端。"""

    def __init__(self, runtime: PluginRuntime) -> None:
        self._runtime = runtime

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = _DEFAULT_HTTP_TIMEOUT,
        max_bytes: int = _MAX_HTTP_BYTES,
    ) -> PluginHTTPResponse:
        """发送 HTTP 请求并读取完整响应体（默认上限 10 MiB）。"""
        session = self._runtime.http
        if session is None:
            async with aiohttp.ClientSession() as temporary:
                return await self._send(
                    temporary, method, url, params, json, data, headers, timeout, max_bytes
                )
        return await self._send(session, method, url, params, json, data, headers, timeout, max_bytes)

    async def _send(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        params: Mapping[str, Any] | None,
        json_body: Any | None,
        data: Any | None,
        headers: Mapping[str, str] | None,
        timeout: float,
        max_bytes: int,
    ) -> PluginHTTPResponse:
        request_timeout = aiohttp.ClientTimeout(total=timeout)
        try:
            async with session.request(
                method.upper(),
                url,
                params=params,
                json=json_body,
                data=data,
                headers=headers,
                timeout=request_timeout,
            ) as response:
                content = await response.content.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise PluginHTTPError(f"响应体超过 {max_bytes} 字节上限: {url}")
                return PluginHTTPResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    content=content,
                )
        except aiohttp.ClientError as exc:
            raise PluginHTTPError(f"HTTP 请求失败: {exc}") from exc
        except TimeoutError as exc:
            raise PluginHTTPError(f"HTTP 请求超时: {url}") from exc

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = _DEFAULT_HTTP_TIMEOUT,
    ) -> PluginHTTPResponse:
        return await self.request("GET", url, params=params, headers=headers, timeout=timeout)

    async def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = _DEFAULT_HTTP_TIMEOUT,
    ) -> PluginHTTPResponse:
        return await self.request("POST", url, json=json, data=data, headers=headers, timeout=timeout)


class PluginAPI:
    """传给 ``setup(api)`` 的插件能力入口。"""

    def __init__(
        self,
        *,
        metadata: Any,
        runtime: PluginRuntime,
        config: Mapping[str, Any],
    ) -> None:
        self._metadata = metadata
        self._runtime = runtime
        self._config = dict(config)
        self._origin = plugin_origin(metadata.name)
        self._unload_handlers: list[PluginUnloadHandler] = []
        self._logger = logging.getLogger(f"sophos.plugin.{metadata.name}")
        self._tools: list[str] = []
        self.protocol = PluginProtocolAPI(runtime)
        self.http = PluginHTTPAPI(runtime)

    # ---- 元信息 ---------------------------------------------------------

    @property
    def name(self) -> str:
        return self._metadata.name

    @property
    def version(self) -> str:
        return self._metadata.version

    @property
    def description(self) -> str:
        return self._metadata.description

    @property
    def author(self) -> str:
        return self._metadata.author

    @property
    def homepage(self) -> str:
        return self._metadata.homepage

    @property
    def metadata(self) -> Any:
        return self._metadata

    @property
    def config(self) -> Mapping[str, Any]:
        """只读的合并配置（插件默认值 + 管理端保存的覆盖值）。"""
        return MappingProxyType(self._config)

    @property
    def logger(self) -> logging.Logger:
        """带 ``sophos.plugin.<name>`` 前缀的 logger。"""
        return self._logger

    @property
    def runtime(self) -> PluginRuntime:
        """宿主运行时（注册表、消息服务、协议路由、连接池等）。"""
        return self._runtime

    @property
    def db(self) -> Any:
        """原始 asyncpg 连接池。

        这是「逃生舱」：插件可以执行任意 SQL。请自行保证查询安全，并注意
        表结构可能随 Sophos 版本变化。没有数据库时抛出 RuntimeError。
        """
        if self._runtime.pool is None:
            raise RuntimeError("当前运行环境没有数据库连接池")
        return self._runtime.pool

    # ---- 工具注册 -------------------------------------------------------

    def tool(
        self,
        *,
        name: str | None = None,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        group: str = "plugin",
        category: str = "input",
        conversation_kinds: frozenset[str] | None = None,
        required_capabilities: frozenset[str] | None = None,
    ) -> Callable[[ToolHandler], FunctionTool]:
        """装饰器：把 async 函数注册成一个工具。

        Example::

            @api.tool(
                name="weather",
                description="查询城市天气",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            )
            async def weather(params, context):
                return {"city": params["city"], "text": "晴，25°C"}
        """

        def decorator(handler: ToolHandler) -> FunctionTool:
            tool_name = name or handler.__name__
            tool_description = description or (handler.__doc__ or tool_name).strip()
            tool = FunctionTool(
                name=tool_name,
                description=tool_description,
                handler=handler,
                parameters=parameters,
                category=category,
                group=group,
                conversation_kinds=conversation_kinds,
                required_capabilities=required_capabilities or frozenset(),
            )
            self.register_tool(tool)
            return tool

        return decorator

    def register_tool(self, tool: Tool) -> Tool:
        """注册一个 Tool 实例（适合需要继承 Tool 的复杂工具）。"""
        self._runtime.registry.register(tool, origin=self._origin)
        if tool.name not in self._tools:
            self._tools.append(tool.name)
        return tool

    def unregister_tool(self, name: str) -> bool:
        """注销本插件注册的工具；不会误删内置或其它插件的工具。"""
        removed = self._runtime.registry.unregister(name, origin=self._origin)
        if removed and name in self._tools:
            self._tools.remove(name)
        return removed

    @property
    def tools(self) -> list[str]:
        """本插件当前注册的工具名列表。"""
        return list(self._tools)

    # ---- 调用内置 / 其它工具 -------------------------------------------

    async def call_tool(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """调用任意已注册工具（内置或其它插件的）。

        没有传 ``context`` 时使用默认上下文（不绑定具体会话）。
        """
        tool_context = dict(context) if context is not None else self._runtime.default_tool_context()
        return await self._runtime.registry.execute(name, dict(params or {}), tool_context)

    # ---- 消息 -----------------------------------------------------------

    async def send_message(
        self,
        text: str,
        *,
        conversation_id: int,
        reply_to_message_id: int | None = None,
        mention_user_ids: tuple[int, ...] = (),
        attachment_ids: tuple[int, ...] = (),
        inline_media: tuple[dict[str, Any], ...] = (),
    ) -> Any:
        """通过平台中立的 MessageService 发送一条消息。

        返回 ``SentMessage(message_id, conversation_id, external_message_id)``。
        需要知道 Sophos 内部的 ``conversation_id``；插件可以从工具上下文或
        数据库里取得。
        """
        service = self._runtime.message_service
        if service is None:
            raise RuntimeError("当前运行环境没有接入消息服务，无法发送消息")
        request = SendMessageRequest(
            conversation_id=conversation_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            mention_user_ids=tuple(mention_user_ids),
            attachment_ids=tuple(attachment_ids),
            inline_media=tuple(inline_media),
        )
        return await service.send_message(request)

    # ---- 生命周期 -------------------------------------------------------

    def on_unload(self, handler: PluginUnloadHandler) -> PluginUnloadHandler:
        """注册卸载回调（关闭自己创建的 HTTP 客户端、后台任务等）。

        回调可以是同步函数或协程函数；在插件被重载 / 停用时按注册顺序的
        逆序执行。
        """
        self._unload_handlers.append(handler)
        return handler

    async def run_unload_handlers(self) -> None:
        """由 PluginManager 调用，执行全部卸载回调。"""
        while self._unload_handlers:
            handler = self._unload_handlers.pop()
            try:
                result = handler()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                self._logger.exception("Plugin unload handler failed")
