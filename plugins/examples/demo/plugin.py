"""示例插件 —— 演示插件系统的主要能力。

把这个目录复制到 ``<PLUGINS_DIR>/demo``（默认是仓库根目录的 ``plugins/demo``），
重启 Sophos 或调用 ``POST /api/plugins/reload`` 即可加载。

演示内容：

1. 用 ``@api.tool`` 注册工具并提供 JSON Schema 参数；
2. 用 ``api.config`` 读取管理端可修改的配置；
3. 用 ``api.call_tool`` 调用内置工具（这里是 ``send_message``）；
4. 用 ``api.protocol.call`` 直接调用协议端（OneBot 11）接口；
5. 用 ``api.on_unload`` 注册卸载回调。

注意：``plugins/examples`` 目录本身不会被扫描（只有 ``plugins/<name>/plugin.py``
或 ``plugins/<name>.py`` 会被加载），所以示例不会自动生效。
"""

from __future__ import annotations

from typing import Any

from sophos.plugins import PluginAPI, PluginMetadata


class DemoPlugin:
    """单文件示例插件；也可以用模块级 ``setup(api)`` 的写法。"""

    metadata = PluginMetadata(
        name="demo",
        version="0.1.0",
        description="示例插件：回声工具、调用内置工具、直连协议端",
        author="baiyu-yu",
        homepage="https://github.com/baiyu-yu/sophos",
        default_config={
            "prefix": "[demo]",
            "allow_protocol_call": True,
        },
    )

    def setup(self, api: PluginAPI) -> None:
        @api.tool(
            name="demo_echo",
            description="把输入文本加上插件配置的前缀后返回，用于验证插件工具是否可用。",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "要回声的文本"},
                },
                "required": ["text"],
            },
        )
        async def demo_echo(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
            prefix = str(api.config.get("prefix", ""))
            return {"text": f"{prefix} {params['text']}".strip()}

        @api.tool(
            name="demo_send_message",
            description="通过内置 send_message 工具发消息，演示调用内置能力与消息服务。",
            parameters={
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "integer", "description": "内部会话 ID"},
                    "text": {"type": "string", "description": "消息内容"},
                },
                "required": ["conversation_id", "text"],
            },
        )
        async def demo_send_message(
            params: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            result = await api.call_tool(
                "send_message",
                {
                    "conversation_id": params["conversation_id"],
                    "text": params["text"],
                },
                context,
            )
            return {"result": result}

        @api.tool(
            name="demo_protocol_call",
            description=(
                "直接调用协议端（OneBot 11）接口，例如 get_group_list、get_group_info、get_login_info。"
                "action 与 params 会原样透传。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "OneBot action，例如 get_group_list"},
                    "params": {
                        "type": "object",
                        "description": "action 参数，例如 {\"group_id\": 123456}",
                    },
                },
                "required": ["action"],
            },
        )
        async def demo_protocol_call(
            params: dict[str, Any], context: dict[str, Any]
        ) -> dict[str, Any]:
            if not api.config.get("allow_protocol_call", True):
                return {"error": "当前插件配置禁止直连协议端"}
            data = await api.protocol.call(params["action"], params.get("params") or {})
            return {"action": params["action"], "data": data}

        def cleanup() -> None:
            api.logger.info("示例插件已卸载")

        api.on_unload(cleanup)

    def teardown(self) -> None:
        """可选：与 setup 对应的清理逻辑（管理器在停用/重载时会调用）。"""


PLUGIN = DemoPlugin()
