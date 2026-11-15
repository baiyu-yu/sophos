"""从上传的 zip / 单文件安装插件到插件目录。

安装只负责把文件安全地放到 ``PLUGINS_DIR``，随后由 :class:`PluginManager`
重新发现并加载。所有路径都经过校验，禁止 ``..``、绝对路径与软链接。
"""

from __future__ import annotations

import io
import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from sophos.plugins.base import PluginInstallError

MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_BYTES = 20 * 1024 * 1024
MAX_ENTRIES = 500
MAX_SINGLE_FILE_BYTES = 1024 * 1024
MAX_NAME_LENGTH = 64

_NAME_RE = re.compile(r"[^\w.\-]", re.UNICODE)


def sanitize_plugin_name(value: str) -> str:
    """把用户提供的名字收敛成安全的目录 / 文件标识。"""
    name = _NAME_RE.sub("-", value.strip()).strip(".-_")
    name = name[:MAX_NAME_LENGTH]
    if not name or name in {".", ".."}:
        raise PluginInstallError("插件名不能为空或包含非法字符")
    return name


def _validate_archive(data: bytes) -> zipfile.ZipFile:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise PluginInstallError(
            f"插件包过大（{len(data)} 字节，上限 {MAX_ARCHIVE_BYTES} 字节）"
        )
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PluginInstallError(f"不是有效的 zip 文件: {exc}") from exc
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise PluginInstallError(f"插件包文件数过多（上限 {MAX_ENTRIES}）")
    total = sum(info.file_size for info in infos)
    if total > MAX_EXTRACTED_BYTES:
        raise PluginInstallError(f"插件解压后过大（上限 {MAX_EXTRACTED_BYTES} 字节）")
    return archive


def _safe_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    raw = info.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw.startswith("/"):
        raise PluginInstallError(f"插件包包含绝对路径: {info.filename}")
    if any(part == ".." for part in path.parts):
        raise PluginInstallError(f"插件包包含路径穿越: {info.filename}")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        raise PluginInstallError(f"插件包包含软链接: {info.filename}")
    return tuple(part for part in path.parts if part not in {"", "."})


def install_zip(
    plugin_dir: Path,
    filename: str,
    data: bytes,
    *,
    overwrite: bool = False,
) -> str:
    """把 zip 安装为目录插件，返回插件目录名。"""
    archive = _validate_archive(data)
    with archive:
        entries: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
        for info in archive.infolist():
            parts = _safe_parts(info)
            if parts:
                entries.append((info, parts))
        if not entries:
            raise PluginInstallError("插件包为空")

        first_parts = {parts[0] for _, parts in entries}
        single_root = (
            len(first_parts) == 1
            and all(len(parts) > 1 for _, parts in entries)
        )
        prefix = next(iter(first_parts)) if single_root else None
        plugin_name = sanitize_plugin_name(prefix or Path(filename).stem)

        def relative(parts: tuple[str, ...]) -> tuple[str, ...]:
            return parts[1:] if prefix is not None else parts

        if not any(relative(parts) == ("plugin.py",) for _, parts in entries):
            raise PluginInstallError("zip 中未找到 plugin.py（应位于包根目录或唯一顶层目录下）")

        plugin_dir.mkdir(parents=True, exist_ok=True)
        target = plugin_dir / plugin_name
        if target.exists() and not overwrite:
            raise PluginInstallError(f"插件 {plugin_name} 已存在，勾选覆盖后重试")

        staging = plugin_dir / f".install-{uuid.uuid4().hex}"
        staging.mkdir(parents=True)
        try:
            root = staging.resolve()
            for info, parts in entries:
                rel = relative(parts)
                if not rel:
                    continue
                destination = staging.joinpath(*rel)
                if not destination.resolve().is_relative_to(root):
                    raise PluginInstallError(f"插件包包含非法路径: {info.filename}")
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

            if not (staging / "plugin.py").is_file():
                raise PluginInstallError("zip 中未找到 plugin.py")

            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            staging.replace(target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return plugin_name


def install_file(
    plugin_dir: Path,
    filename: str,
    data: bytes,
    *,
    overwrite: bool = False,
) -> str:
    """把单个 ``.py`` 文件安装为单文件插件，返回插件文件名（不含后缀）。"""
    if not filename.lower().endswith(".py"):
        raise PluginInstallError("仅支持 .zip 插件包或 .py 单文件插件")
    if len(data) > MAX_SINGLE_FILE_BYTES:
        raise PluginInstallError(f"插件文件过大（上限 {MAX_SINGLE_FILE_BYTES} 字节）")
    if b"\x00" in data:
        raise PluginInstallError("插件文件不是合法的文本文件")

    plugin_name = sanitize_plugin_name(Path(filename).stem)
    plugin_dir.mkdir(parents=True, exist_ok=True)
    target = plugin_dir / f"{plugin_name}.py"
    if target.exists() and not overwrite:
        raise PluginInstallError(f"插件 {plugin_name} 已存在，勾选覆盖后重试")
    directory = plugin_dir / plugin_name
    if directory.exists():
        raise PluginInstallError(f"已存在同名插件目录 {plugin_name}")

    target.write_bytes(data)
    return plugin_name


def remove_installed(plugin_dir: Path, name: str, path: Path, *, source: str) -> None:
    """删除已安装的插件文件；只允许删除插件目录内的内容。"""
    if source == "entry_point":
        raise PluginInstallError("entry point 安装的插件不能通过 WebUI 删除")
    target = path.parent if source == "directory" else path
    root = plugin_dir.resolve()
    resolved = target.resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise PluginInstallError(f"拒绝删除插件目录之外的文件: {target}")
    if resolved == root:
        raise PluginInstallError("拒绝删除整个插件目录")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


__all__ = [
    "MAX_ARCHIVE_BYTES",
    "MAX_ENTRIES",
    "MAX_EXTRACTED_BYTES",
    "MAX_SINGLE_FILE_BYTES",
    "install_file",
    "install_zip",
    "remove_installed",
    "sanitize_plugin_name",
]
