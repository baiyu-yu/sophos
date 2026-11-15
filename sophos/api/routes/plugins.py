"""插件管理 API。"""

from aiohttp import web

from sophos.plugins import PluginError, PluginInstallError, PluginManager, PluginNotFoundError
from sophos.plugins.loader import LoadedPlugin

routes = web.RouteTableDef()


def _manager(request: web.Request) -> PluginManager:
    manager: PluginManager | None = request.app.get("plugin_manager")
    if manager is None:
        raise web.HTTPServiceUnavailable(reason="plugin manager not available")
    return manager


def _respond(
    manager: PluginManager,
    record: LoadedPlugin,
    message: str,
    *,
    status: int = 200,
) -> web.Response:
    return web.json_response({"message": message, "plugin": manager.describe(record)}, status=status)


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


async def _read_upload(request: web.Request, *, limit: int) -> tuple[str, bytes]:
    """读取 multipart 中的 ``file`` 字段，边读边限制大小。"""
    if not request.content_type.startswith("multipart/"):
        raise web.HTTPBadRequest(reason="请使用 multipart/form-data 上传插件文件")
    reader = await request.multipart()
    filename: str | None = None
    data = bytearray()
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name != "file":
            await part.read()
            continue
        if not part.filename:
            raise web.HTTPBadRequest(reason="上传字段 file 缺少文件名")
        filename = part.filename
        size = 0
        while True:
            chunk = await part.read_chunk(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise web.HTTPRequestEntityTooLarge(
                    max_size=limit,
                    actual_size=size,
                    reason=f"插件文件过大（上限 {limit} 字节）",
                )
            data.extend(chunk)
    if filename is None:
        raise web.HTTPBadRequest(reason="缺少上传字段 file")
    return filename, bytes(data)


@routes.get("/api/plugins")
async def list_plugins(request: web.Request) -> web.Response:
    """列出所有已发现的插件及其状态、配置和注册的工具。"""
    manager = _manager(request)
    return web.json_response({"plugins": manager.list_plugins(), "plugins_dir": str(manager.plugins_dir)})


@routes.post("/api/plugins/upload")
async def upload_plugin(request: web.Request) -> web.Response:
    """上传 ``.zip``（目录插件）或 ``.py``（单文件插件）并立即加载。"""
    manager = _manager(request)
    filename, data = await _read_upload(request, limit=16 * 1024 * 1024)
    overwrite = _truthy(request.query.get("overwrite"))
    try:
        if filename.lower().endswith(".zip"):
            record = await manager.install_zip(filename, data, overwrite=overwrite)
        elif filename.lower().endswith(".py"):
            record = await manager.install_file(filename, data, overwrite=overwrite)
        else:
            raise web.HTTPBadRequest(reason="仅支持 .zip 插件包或 .py 单文件插件")
    except PluginInstallError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    except PluginError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return _respond(manager, record, f"插件 '{record.name}' 已安装", status=201)


@routes.put("/api/plugins/{name}/enabled")
async def set_plugin_enabled(request: web.Request) -> web.Response:
    """启用/停用插件；启用会立即加载插件并注册其工具。"""
    manager = _manager(request)
    name = request.match_info["name"]
    payload = await request.json()
    enabled = bool(payload.get("enabled", True))
    try:
        record = await manager.set_enabled(name, enabled)
    except PluginNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except PluginError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return _respond(manager, record, f"插件 '{name}' 已{'启用' if enabled else '停用'}")


@routes.put("/api/plugins/{name}/config")
async def set_plugin_config(request: web.Request) -> web.Response:
    """覆盖插件配置；启用中的插件会自动重载以应用配置。"""
    manager = _manager(request)
    name = request.match_info["name"]
    payload = await request.json()
    config = payload.get("config", {})
    if not isinstance(config, dict):
        raise web.HTTPBadRequest(reason="config 必须是 JSON 对象")
    try:
        record = await manager.set_config(name, config)
    except PluginNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except PluginError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return _respond(manager, record, f"插件 '{name}' 配置已更新")


@routes.delete("/api/plugins/{name}")
async def uninstall_plugin(request: web.Request) -> web.Response:
    """删除插件文件并清理其持久化状态。"""
    manager = _manager(request)
    name = request.match_info["name"]
    try:
        await manager.uninstall(name)
    except PluginNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except PluginError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return web.json_response({"message": f"插件 '{name}' 已删除", "plugins": manager.list_plugins()})


@routes.post("/api/plugins/reload")
async def reload_plugins(request: web.Request) -> web.Response:
    """重新扫描插件目录并重载全部插件。"""
    manager = _manager(request)
    await manager.reload()
    return web.json_response({"message": "插件已重新加载", "plugins": manager.list_plugins()})


@routes.post("/api/plugins/{name}/reload")
async def reload_plugin(request: web.Request) -> web.Response:
    """重载单个插件。"""
    manager = _manager(request)
    name = request.match_info["name"]
    try:
        record = await manager.reload_plugin(name)
    except PluginNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except PluginError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return _respond(manager, record, f"插件 '{name}' 已重新加载")
