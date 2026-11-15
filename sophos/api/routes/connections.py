"""OneBot 连接管理 API。"""

from __future__ import annotations

from typing import Any

from aiohttp import web

from sophos.connections import (
    ConnectionManagerError,
    ConnectionNotFoundError,
    ConnectionValidationError,
    OneBotConnectionManager,
)

routes = web.RouteTableDef()


def _manager(request: web.Request) -> OneBotConnectionManager:
    manager: OneBotConnectionManager | None = request.app.get("connection_manager")
    if manager is None:
        raise web.HTTPServiceUnavailable(reason="connection manager not available")
    return manager


def _connection_id(request: web.Request) -> int:
    raw = request.match_info["connection_id"]
    try:
        return int(raw)
    except ValueError as exc:
        raise web.HTTPBadRequest(reason="连接 ID 必须是整数") from exc


async def _payload(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise web.HTTPBadRequest(reason="请求体必须是 JSON 对象") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(reason="请求体必须是 JSON 对象")
    return payload


def _bool_field(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise web.HTTPBadRequest(reason=f"{key} 必须是布尔值")


def _int_field(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise web.HTTPBadRequest(reason=f"{key} 必须是整数")
    return value


def _str_field(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise web.HTTPBadRequest(reason=f"{key} 必须是字符串")
    return value


@routes.get("/api/connections")
async def list_connections(request: web.Request) -> web.Response:
    """列出所有 OneBot 连接及其实时状态（token 只返回是否已配置）。"""
    manager = _manager(request)
    return web.json_response({"connections": manager.list_connections()})


@routes.post("/api/connections")
async def create_connection(request: web.Request) -> web.Response:
    """新增连接；enabled 为 true 时立即开始连接。"""
    manager = _manager(request)
    payload = await _payload(request)
    name = _str_field(payload, "name") or ""
    ws_url = _str_field(payload, "ws_url") or ""
    token = _str_field(payload, "token") or ""
    interval = _int_field(payload, "reconnect_interval")
    try:
        connection = await manager.create_connection(
            name=name,
            ws_url=ws_url,
            token=token,
            enabled=_bool_field(payload, "enabled") if "enabled" in payload else True,
            auto_reconnect=_bool_field(payload, "auto_reconnect") if "auto_reconnect" in payload else True,
            reconnect_interval=5 if interval is None else interval,
        )
    except ConnectionValidationError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return web.json_response({"message": f"连接 '{connection['name']}' 已创建", "connection": connection}, status=201)


@routes.put("/api/connections/{connection_id}")
async def update_connection(request: web.Request) -> web.Response:
    """更新连接；运行中的连接会自动重连以应用新参数。token 留空表示不修改。"""
    manager = _manager(request)
    connection_id = _connection_id(request)
    payload = await _payload(request)
    token = _str_field(payload, "token")
    try:
        connection = await manager.update_connection(
            connection_id,
            name=_str_field(payload, "name"),
            ws_url=_str_field(payload, "ws_url"),
            token=token,
            enabled=_bool_field(payload, "enabled"),
            auto_reconnect=_bool_field(payload, "auto_reconnect"),
            reconnect_interval=_int_field(payload, "reconnect_interval"),
        )
    except ConnectionNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except ConnectionValidationError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc
    return web.json_response({"message": "连接已更新", "connection": connection})


@routes.delete("/api/connections/{connection_id}")
async def delete_connection(request: web.Request) -> web.Response:
    """删除连接并停止重连。"""
    manager = _manager(request)
    connection_id = _connection_id(request)
    try:
        await manager.delete_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    return web.json_response({"message": "连接已删除", "connections": manager.list_connections()})


@routes.post("/api/connections/{connection_id}/start")
async def start_connection(request: web.Request) -> web.Response:
    """开始连接（同时把 enabled 置为 true）。"""
    manager = _manager(request)
    connection_id = _connection_id(request)
    try:
        connection = await manager.start_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    return web.json_response({"message": "正在连接", "connection": connection})


@routes.post("/api/connections/{connection_id}/stop")
async def stop_connection(request: web.Request) -> web.Response:
    """停止连接并终止自动重连，直到再次启动。"""
    manager = _manager(request)
    connection_id = _connection_id(request)
    try:
        connection = await manager.stop_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    return web.json_response({"message": "已停止", "connection": connection})


@routes.post("/api/connections/{connection_id}/restart")
async def restart_connection(request: web.Request) -> web.Response:
    """立即断开并重新连接。"""
    manager = _manager(request)
    connection_id = _connection_id(request)
    try:
        connection = await manager.restart_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    return web.json_response({"message": "正在重连", "connection": connection})


__all__ = ["ConnectionManagerError", "routes"]
