"""运行时可调配置 API。

暴露 ``runtime_config`` 中登记的全部配置项：WebUI「设置」页据此渲染表单，
保存后立即写入 DB 并刷新缓存（个别项标注 requires_restart）。
"""

from typing import Any

from aiohttp import web

from sophos import runtime_config

routes = web.RouteTableDef()


def _bad_request(message: str) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(reason=message)


@routes.get("/api/settings")
async def list_settings(request: web.Request) -> web.Response:
    """返回全部可编辑配置的当前值与元信息。"""
    values = runtime_config.get_all()
    specs = runtime_config.list_specs()
    exposed: dict[str, Any] = {}
    for spec in specs:
        key = spec["key"]
        value = values.get(key)
        if spec.get("secret") and isinstance(value, str) and value:
            exposed[key] = "********"
        else:
            exposed[key] = value
    return web.json_response(
        {
            "settings": exposed,
            "specs": [
                {**spec, "default": "********" if spec.get("secret") and spec.get("default") else spec["default"]}
                for spec in specs
            ],
            "groups": runtime_config.group_order(),
        }
    )


@routes.put("/api/settings/{key}")
async def update_setting(request: web.Request) -> web.Response:
    """修改单个运行配置。"""
    key = request.match_info["key"]
    try:
        payload = await request.json()
    except ValueError as exc:
        raise _bad_request("请求体必须是 JSON") from exc
    if not isinstance(payload, dict) or "value" not in payload:
        raise _bad_request("请求体需要包含 value 字段")
    try:
        value = runtime_config.validate_value(key, payload["value"])
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    await runtime_config.set_value(key, value)
    spec = next((item for item in runtime_config.list_specs() if item["key"] == key), None)
    display = "********" if spec and spec.get("secret") and value else value
    message = f"{spec['label'] if spec else key} 已更新"
    if spec and spec.get("requires_restart"):
        message += "，重启后生效"
    return web.json_response({"message": message, "value": display})


@routes.delete("/api/settings/{key}")
async def reset_setting(request: web.Request) -> web.Response:
    """恢复配置默认值。"""
    key = request.match_info["key"]
    if key not in runtime_config.get_defaults():
        raise _bad_request(f"未知配置项: {key}")
    await runtime_config.delete(key)
    spec = next((item for item in runtime_config.list_specs() if item["key"] == key), None)
    value = runtime_config.get(key)
    display = "********" if spec and spec.get("secret") and value else value
    return web.json_response({"message": f"{spec['label'] if spec else key} 已恢复默认", "value": display})
