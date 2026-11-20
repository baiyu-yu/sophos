"""自定义图床上传：把本地图片上传到用户配置的图床，换取长期可用的 URL。"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from sophos import media, runtime_config

logger = logging.getLogger(__name__)


class ImageHostError(RuntimeError):
    """图床未配置或上传失败。"""


def _url_from_payload(payload: Any) -> str | None:
    """从常见图床返回结构里找出图片 URL。"""
    if isinstance(payload, str):
        return payload if payload.startswith(("http://", "https://")) else None
    if isinstance(payload, list):
        for item in payload:
            found = _url_from_payload(item)
            if found:
                return found
        return None
    if not isinstance(payload, dict):
        return None
    for key in ("url", "link", "src", "image", "img", "image_url"):
        found = _url_from_payload(payload.get(key))
        if found:
            return found
    for key in ("data", "result", "results", "files", "images"):
        if key in payload:
            found = _url_from_payload(payload[key])
            if found:
                return found
    for value in payload.values():
        found = _url_from_payload(value)
        if found:
            return found
    return None


async def upload_image(
    data: bytes,
    *,
    filename: str,
    mime_type: str,
    session: aiohttp.ClientSession | None = None,
) -> str:
    """上传图片到配置的图床，返回 URL。"""
    endpoint = str(runtime_config.get("image_host_url") or "").strip()
    if not endpoint:
        raise ImageHostError("未配置图床地址（设置 → 图片 → 图床地址）")

    field = str(runtime_config.get("image_host_field") or "file").strip() or "file"
    timeout = float(runtime_config.get("image_host_timeout") or 30.0)
    headers: dict[str, str] = {}
    token = str(runtime_config.get("image_host_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    form = aiohttp.FormData()
    form.add_field(field, data, filename=filename, content_type=mime_type)

    owns_session = session is None
    if session is None:
        session = aiohttp.ClientSession()
    try:
        async with session.post(
            endpoint,
            data=form,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            body = await response.text()
            if response.status >= 400:
                raise ImageHostError(f"图床返回 HTTP {response.status}: {body[:200]}")
    except aiohttp.ClientError as exc:
        raise ImageHostError(f"图床请求失败: {exc}") from exc
    except TimeoutError as exc:
        raise ImageHostError(f"图床上传超时（{timeout:.0f} 秒）") from exc
    finally:
        if owns_session:
            await session.close()

    try:
        payload: Any = json.loads(body)
    except ValueError:
        payload = body
    url = _url_from_payload(payload)
    if not url:
        raise ImageHostError(f"图床响应里没有图片 URL: {body[:200]}")
    logger.info("图片已上传图床 url=%s", url)
    return url


async def upload_local_image(value: Any, *, session: aiohttp.ClientSession | None = None) -> dict[str, Any]:
    """上传本地已保存的图片，返回 {code, path, url}。"""
    found = media.read_image(value)
    if found is None:
        raise ImageHostError("图片编码不存在或尚未保存到本地")
    code, path, data = found
    url = await upload_image(
        data,
        filename=path.name,
        mime_type=media.mime_for_path(path),
        session=session,
    )
    return {"code": code, "path": str(path), "url": url}
