"""联网工具 — Tavily 搜索/提取 + 图片查看。"""

import logging
import math
from typing import Any

import aiohttp

from sophos import observability, runtime_config
from sophos.tools.base import Tool

logger = logging.getLogger(__name__)

_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
_IMAGE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


async def _tavily_request(tool: str, url: str, payload: dict, context: dict) -> dict:
    values = {"conversation_id": context["conversation_id"]} if "conversation_id" in context else {}
    with observability.scope(**values):
        async with observability.tool_call(tool, provider="tavily") as call:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json={**payload, "include_usage": True}, timeout=aiohttp.ClientTimeout(total=30),
                ) as resp,
            ):
                if resp.status != 200:
                    call.error = f"HTTP {resp.status}"
                    return {"error": f"Tavily {tool} failed ({resp.status})"}
                data = await resp.json()
            credit_usage = (data.get("usage") or {}).get("credits")
            if (
                isinstance(credit_usage, (int, float)) and not isinstance(credit_usage, bool)
                and math.isfinite(credit_usage) and credit_usage >= 0
            ):
                call.credits = float(credit_usage)
            if data.get("failed_results"):
                call.error = f"{len(data['failed_results'])} 个页面提取失败"
            if data.get("error"):
                call.error = "Tavily 返回错误"
            return data


class WebSearchTool(Tool):
    """Tavily 联网搜索。"""

    @property
    def group(self) -> str:
        return "web"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "联网搜索。返回搜索结果列表和可选的 AI 摘要。"
            "search_depth 可选 basic（快速）或 advanced（更详细，消耗更多额度）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": "搜索深度，默认 basic",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        api_key = runtime_config.get("tavily_api_key")
        if not api_key:
            return {"error": "tavily_api_key 未配置"}
        payload = {
            "api_key": api_key,
            "query": params["query"],
            "search_depth": params.get("search_depth", "basic"),
            "max_results": runtime_config.get("tavily_max_results"),
            "include_answer": runtime_config.get("tavily_include_answer"),
        }
        data = await _tavily_request(self.name, _TAVILY_SEARCH_URL, payload, context)
        if data.get("error"):
            return {"error": data["error"]}
        results = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in data.get("results", [])
        ]
        out: dict[str, Any] = {"results": results}
        if data.get("answer"):
            out["answer"] = data["answer"]
        return out


class WebFetchTool(Tool):
    """Tavily 网页内容提取。"""

    @property
    def group(self) -> str:
        return "web"

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "获取网页正文内容。传入 URL 列表（最多 5 个），返回各页面的提取文本。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要提取内容的 URL 列表，最多 5 个",
                },
            },
            "required": ["urls"],
        }

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        api_key = runtime_config.get("tavily_api_key")
        if not api_key:
            return {"error": "tavily_api_key 未配置"}
        urls = params["urls"][:5]
        payload = {"api_key": api_key, "urls": urls}
        data = await _tavily_request(self.name, _TAVILY_EXTRACT_URL, payload, context)
        if data.get("error"):
            return {"error": data["error"]}
        results = [{"url": r.get("url", ""), "content": r.get("raw_content", "")} for r in data.get("results", [])]
        failed = data.get("failed_results", [])
        out: dict[str, Any] = {"results": results}
        if failed:
            out["failed"] = [{"url": f.get("url", ""), "error": f.get("error", "")} for f in failed]
        return out


class ViewImageTool(Tool):
    """抓取网络图片并通过 VLM 描述。"""

    @property
    def group(self) -> str:
        return "vision"

    @property
    def name(self) -> str:
        return "view_image"

    @property
    def description(self) -> str:
        return (
            "查看图片并返回视觉描述。传 url 抓取网络图片，或传 image_code 查看已保存的图片"
            "（上下文里的 [图片(hash): …] 中的 hash）；网络图片会顺带保存到本地并返回 code。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "图片 URL（与 image_code 二选一）"},
                "image_code": {
                    "type": "string",
                    "description": "已保存图片的编码（与 url 二选一）",
                },
            },
        }

    async def execute(self, params: dict[str, Any], context: dict[str, Any]) -> Any:
        vision_provider = context.get("vision_provider")
        if not vision_provider:
            return {"error": "vision provider 未配置"}
        code = ""
        url = str(params.get("url") or "").strip()
        image_code = str(params.get("image_code") or "").strip()

        if image_code:
            from sophos import media

            found = media.read_image(image_code)
            if found is None:
                return {"error": "图片编码不存在或尚未保存到本地"}
            code, _path, data = found
            mime_type = media.mime_for_path(_path)
        elif url:
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp,
                ):
                    if resp.status != 200:
                        return {"error": f"HTTP {resp.status}"}
                    ct = resp.content_type or ""
                    if not ct.startswith("image/"):
                        return {"error": f"非图片类型: {ct}"}
                    data = await resp.read()
                    if len(data) > _IMAGE_MAX_BYTES:
                        return {"error": "图片过大（>10MB）"}
            except Exception as e:
                return {"error": f"抓取失败: {e}"}
            mime_type = ct.split(";")[0].strip()
        else:
            return {"error": "必须提供 url 或 image_code"}

        from sophos import media
        from sophos.vision import compute_hash, describe_image

        path = None
        if not image_code:
            try:
                hash_str = await compute_hash(data)
                if hash_str:
                    saved = media.save_image_bytes(data, mime_type, code=hash_str)
                    if saved:
                        code = saved
                        path = str(media.find_image(saved) or "")
            except Exception as exc:  # 落盘失败不影响描述
                logger.warning("view_image 保存图片失败: %s", exc)

        try:
            desc = await describe_image(vision_provider, data, mime_type)
        except Exception as e:
            logger.warning("VLM describe_image failed: %s", e)
            return {"error": f"VLM 描述失败: {e}"}
        out: dict[str, Any] = {"description": desc}
        if code:
            out["code"] = code
            if path:
                out["saved_path"] = path
        return out


WEB_TOOLS: list[Tool] = [
    WebSearchTool(),
    WebFetchTool(),
    ViewImageTool(),
]
