"""图片工具：按图片编码发送本地图片、查询/上传图片。"""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

from sophos import image_host, media, runtime_config
from sophos.platform import Capability, SendMessageRequest
from sophos.tools.base import Tool

logger = logging.getLogger(__name__)

_MISSING_CODE_HINT = (
    "没有找到该图片编码对应的本地文件。图片编码来自上下文里的 [图片(<hash>): 描述]，"
    "只有图片下载成功（或通过 view_image / save_image 保存过）的编码才能使用。"
)


def _caption(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null", "无"} else text


class SendImageTool(Tool):
    """按图片编码把本地图片发回当前对话。"""

    @property
    def category(self) -> str:
        return "output"

    @property
    def group(self) -> str:
        return "vision"

    @property
    def required_capabilities(self) -> frozenset[str]:
        return frozenset({Capability.MESSAGE_SEND.value, Capability.MESSAGE_IMAGE.value})

    @property
    def name(self) -> str:
        return "send_image"

    @property
    def description(self) -> str:
        return (
            "发送本地已保存的图片。image_code 取自上下文中的 [图片(<hash>): 描述] 里的 hash，"
            "或 view_image/save_image 返回的 code；不要再传图片 URL。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_code": {
                    "type": "string",
                    "description": "图片编码（上下文 [图片(hash): …] 中的 hash）",
                },
                "text": {
                    "type": "string",
                    "description": "可选：随图片一起发送的文字说明",
                },
                "conversation_id": {
                    "type": "integer",
                    "description": "可选：目标会话 ID，默认当前会话",
                },
                "reply_to_message_id": {
                    "type": "integer",
                    "description": "可选：要回复的消息 ID；不需要回复时省略",
                },
            },
            "required": ["image_code"],
        }

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        found = media.read_image(params.get("image_code"))
        if found is None:
            return {"error": _MISSING_CODE_HINT}
        code, path, data = found
        conversation_id = params.get("conversation_id") or context.get("conversation_id")
        if not conversation_id:
            return {"error": "缺少 conversation_id"}
        reply_to = params.get("reply_to_message_id")
        try:
            reply_to = int(reply_to) if reply_to is not None else None
        except (TypeError, ValueError):
            reply_to = None

        message_service = context.get("message_service")
        if message_service is None:
            return {"error": "消息服务未就绪"}

        payload = {
            "type": "image",
            "data": {"base64": base64.b64encode(data).decode("ascii")},
        }
        try:
            sent = await message_service.send_message(
                SendMessageRequest(
                    conversation_id=int(conversation_id),
                    text=_caption(params.get("text")),
                    reply_to_message_id=reply_to,
                    inline_media=(payload,),
                )
            )
        except Exception as exc:
            logger.warning("send_image 失败 code=%s: %s", code, exc)
            return {"error": f"发送图片失败: {exc}"}
        return {
            "status": "ok",
            "image_code": code,
            "path": str(path),
            "message_id": sent.message_id,
        }


class SaveImageTool(Tool):
    """确认图片编码并返回本地路径；可选上传到自定义图床换取长期 URL。"""

    @property
    def group(self) -> str:
        return "vision"

    @property
    def name(self) -> str:
        return "save_image"

    @property
    def description(self) -> str:
        return (
            "保存/导出图片。传入图片编码返回本地文件路径与（配置了对外地址时的）URL；"
            "upload=true 时上传到已配置的图床，返回可长期使用的图片 URL。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_code": {
                    "type": "string",
                    "description": "图片编码（上下文 [图片(hash): …] 中的 hash）",
                },
                "upload": {
                    "type": "boolean",
                    "description": "是否上传到图床（需要先在设置里配置图床地址）",
                },
            },
            "required": ["image_code"],
        }

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        found = media.read_image(params.get("image_code"))
        if found is None:
            return {"error": _MISSING_CODE_HINT}
        code, path, data = found
        upload = bool(params.get("upload"))
        url = media.public_url(code)
        if not upload:
            return {
                "status": "ok",
                "image_code": code,
                "path": str(path),
                "bytes": len(data),
                "url": url,
                "note": "图片已在本地保存；如需长期可用的外链，设置图床后用 upload=true 上传。"
                if not url
                else "图片已在本地保存，url 为对外访问地址。",
            }

        if not str(runtime_config.get("image_host_url") or "").strip():
            return {"error": "未配置图床地址（设置 → 图片 → 图床地址），无法上传"}
        try:
            async with aiohttp.ClientSession() as session:
                result = await image_host.upload_local_image(code, session=session)
        except image_host.ImageHostError as exc:
            return {"error": str(exc)}
        return {"status": "ok", "uploaded": True, **result}


MEDIA_TOOLS: list[Tool] = [
    SendImageTool(),
    SaveImageTool(),
]
