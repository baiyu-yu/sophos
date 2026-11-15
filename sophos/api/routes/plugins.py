"""插件管理 API。"""

from aiohttp import web

from sophos.plugins import PluginError, PluginManager, PluginNotFoundError
from sophos.plugins.loader import LoadedPlugin

routes = web.RouteTableDef()


def _manager(request: web.Request) -> PluginManager:
    manager: PluginManager | None = request.app.get("plugin_manager")
    if manager is None:
        raise web.HTTPServiceUnavailable(reason="plugin manager not available")
    return manager


def _respond(manager: PluginManager, record: LoadedPlugin, message: str) -> web.Response:
    return web.json_response({"message": message, "plugin": manager.describe(record)})


@routes.get("/api/plugins")
async def list_plugins(request: web.Request) -> web.Response:
    """列出所有已发现的插件及其状态、配置和注册的工具。"""
    manager = _manager(request)
    return web.json_response({"plugins": manager.list_plugins(), "plugins_dir": str(manager.plugins_dir)})


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
