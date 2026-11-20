"""图片等媒体文件的本地存储与「图片编码」解析。

上下文里展示的 ``[图片(<hash>): 描述]`` 里的 ``<hash>`` 就是图片编码：图片识别阶段
会把原始字节落盘到 ``media_dir``，之后模型可以用该编码重新发送图片或上传到图床，
不再依赖 QQ 的临时 URL。
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

from sophos import runtime_config

logger = logging.getLogger(__name__)

# 单张图片落盘上限，避免把异常大的文件写到磁盘。
MAX_IMAGE_BYTES = 20 * 1024 * 1024

# 图片编码：imagehash 的十六进制字符串（默认 16 位），也接受 sha256 前缀。
_CODE_RE = re.compile(r"[0-9a-f]{8,64}")

# 对外提供的文件名白名单，防止路径穿越。
FILENAME_RE = re.compile(r"^[0-9a-f]{8,64}\.(?:png|jpg|jpeg|gif|webp)$")

_MIME_EXTENSIONS: dict[str, str] = {
    "image/png": "png",
    "image/apng": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/pjpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}

_EXTENSION_MIME: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def media_root() -> Path:
    """返回媒体目录（未创建）。"""
    raw = str(runtime_config.get("media_dir") or "data/media").strip() or "data/media"
    return Path(raw).expanduser()


def normalize_code(value: Any) -> str | None:
    """从 ``abc123`` / ``[图片(abc123): …]`` 之类的输入里取出图片编码。"""
    if value is None:
        return None
    match = _CODE_RE.search(str(value).strip().lower())
    return match.group(0) if match else None


def code_for_bytes(data: bytes) -> str:
    """没有感知哈希时用内容摘要作为编码。"""
    return hashlib.sha256(data).hexdigest()[:16]


def extension_for_mime(mime_type: str) -> str | None:
    normalized = (mime_type or "").split(";")[0].strip().lower()
    return _MIME_EXTENSIONS.get(normalized)


def mime_for_path(path: Path) -> str:
    return _EXTENSION_MIME.get(path.suffix.lower().lstrip("."), "image/png")


def save_image_bytes(data: bytes, mime_type: str, *, code: str | None = None) -> str | None:
    """把图片字节原子写入媒体目录，返回图片编码；失败返回 None。"""
    if not data:
        return None
    if len(data) > MAX_IMAGE_BYTES:
        logger.warning("图片过大（%d 字节），不落盘", len(data))
        return None

    extension = extension_for_mime(mime_type)
    if extension is None:
        logger.warning("不支持的图片类型 %r，不落盘", mime_type)
        return None

    normalized = normalize_code(code) or code_for_bytes(data)
    root = media_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("创建媒体目录 %s 失败: %s", root, exc)
        return None

    target = root / f"{normalized}.{extension}"
    if target.is_file() and target.stat().st_size == len(data):
        return normalized

    temporary = root / f".{normalized}-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
        os.replace(temporary, target)
    except OSError as exc:
        logger.warning("写入图片 %s 失败: %s", target, exc)
        temporary.unlink(missing_ok=True)
        return None
    logger.debug("图片已保存 path=%s bytes=%d", target, len(data))
    return normalized


def find_image(value: Any) -> Path | None:
    """按图片编码查找本地文件。"""
    code = normalize_code(value)
    if code is None:
        return None
    root = media_root()
    for extension in _EXTENSION_MIME:
        candidate = root / f"{code}.{extension}"
        if candidate.is_file():
            return candidate
    return None


def public_url(value: Any) -> str:
    """返回配置了 ``media_public_base_url`` 时的对外访问地址，否则空串。"""
    base = str(runtime_config.get("media_public_base_url") or "").strip().rstrip("/")
    if not base:
        return ""
    path = find_image(value)
    if path is None:
        return ""
    return f"{base}/{path.name}"


def read_image(value: Any) -> tuple[str, Path, bytes] | None:
    """读取图片，返回 (编码, 路径, 字节)；不存在返回 None。"""
    path = find_image(value)
    if path is None:
        return None
    try:
        data = path.read_bytes()
    except OSError as exc:
        logger.warning("读取图片 %s 失败: %s", path, exc)
        return None
    return path.stem, path, data
