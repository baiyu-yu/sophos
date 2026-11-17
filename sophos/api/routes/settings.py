"""运行时可调配置 API（命令前缀、触发正则等）。"""

import re
from typing import Any

from aiohttp import web

from sophos import runtime_config

routes = web.RouteTableDef()

# 允许从 WebUI 读写的配置项；不要在此暴露 API Key 等敏感值。
_EXPOSED_KEYS = ("command_prefix", "trigger_regexes")
_MAX_COMMAND_PREFIX_LENGTH = 3
_MAX_REGEX_COUNT = 50
_MAX_REGEX_LENGTH = 200


def _validate_command_prefix(value: Any) -> str:
    if not isinstance(value, str):
        raise web.HTTPBadRequest(reason="命令前缀必须是字符串")
    prefix = value.strip()
    if not prefix:
        raise web.HTTPBadRequest(reason="命令前缀不能为空")
    if len(prefix) > _MAX_COMMAND_PREFIX_LENGTH:
        raise web.HTTPBadRequest(
            reason=f"命令前缀最多 {_MAX_COMMAND_PREFIX_LENGTH} 个字符"
        )
    if any(char.isspace() for char in prefix):
        raise web.HTTPBadRequest(reason="命令前缀不能包含空白字符")
    return prefix


def _validate_trigger_regexes(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise web.HTTPBadRequest(reason="触发正则必须是字符串数组")
    patterns: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise web.HTTPBadRequest(reason="触发正则必须是字符串数组")
        pattern = item.strip()
        if not pattern:
            continue
        if len(pattern) > _MAX_REGEX_LENGTH:
            raise web.HTTPBadRequest(
                reason=f"单条正则最多 {_MAX_REGEX_LENGTH} 个字符: {pattern[:30]}…"
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise web.HTTPBadRequest(reason=f"正则无效: {pattern}（{exc}）") from exc
        patterns.append(pattern)
    if len(patterns) > _MAX_REGEX_COUNT:
        raise web.HTTPBadRequest(reason=f"最多配置 {_MAX_REGEX_COUNT} 条触发正则")
    return patterns


def _validate(key: str, value: Any) -> Any:
    if key == "command_prefix":
        return _validate_command_prefix(value)
    if key == "trigger_regexes":
        return _validate_trigger_regexes(value)
    raise web.HTTPBadRequest(reason=f"配置项 '{key}' 不支持 WebUI 修改")


@routes.get("/api/settings")
async def list_settings(request: web.Request) -> web.Response:
    """返回可编辑的运行配置。"""
    values = runtime_config.get_all()
    return web.json_response({"settings": {key: values.get(key) for key in _EXPOSED_KEYS}})


@routes.put("/api/settings/{key}")
async def update_setting(request: web.Request) -> web.Response:
    """修改单个运行配置。"""
    key = request.match_info["key"]
    try:
        payload = await request.json()
    except ValueError as exc:
        raise web.HTTPBadRequest(reason="请求体必须是 JSON") from exc
    if not isinstance(payload, dict) or "value" not in payload:
        raise web.HTTPBadRequest(reason="请求体需要包含 value 字段")
    value = _validate(key, payload["value"])
    await runtime_config.set_value(key, value)
    return web.json_response({"message": f"{key} 已更新", "value": value})


@routes.delete("/api/settings/{key}")
async def reset_setting(request: web.Request) -> web.Response:
    """恢复配置默认值。"""
    key = request.match_info["key"]
    if key not in _EXPOSED_KEYS:
        raise web.HTTPBadRequest(reason=f"配置项 '{key}' 不支持 WebUI 修改")
    await runtime_config.delete(key)
    return web.json_response({"message": f"{key} 已恢复默认", "value": runtime_config.get(key)})
