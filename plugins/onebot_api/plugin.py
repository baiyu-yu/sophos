"""OneBot 11 通用接口调用插件。

让模型可以自主调用协议端（NapCat / Lagrange / go-cqhttp / LLOneBot 等）的任意
OneBot 11 接口。内置工具已经覆盖的能力（发消息、撤回、群成员列表、踢人/禁言、
改群名）默认被屏蔽，统一走内置工具，避免绕过消息入库与会话权限。

插件配置（WebUI 插件页 → 配置）：
  - blocked_actions: 禁止调用的 action 列表，默认屏蔽内置工具已覆盖的 6 个
  - timeout:         单次调用超时秒数（1–120，默认 30）
  - max_result_chars: 返回结果最大字符数，超出截断（1000–200000，默认 12000）
"""

from __future__ import annotations

import json
from typing import Any

from sophos.plugins import PluginAPI, PluginMetadata

# 内置工具已经覆盖的 action：默认禁止，避免出现两条发送/管理路径。
DEFAULT_BLOCKED_ACTIONS = [
    "send_msg",
    "delete_msg",
    "get_group_member_list",
    "set_group_kick",
    "set_group_ban",
    "set_group_name",
]

_ACTION_CATALOG = """\
常用 action（参数名与协议端文档一致；不同实现的可用集合略有差异）：
- 查询：get_status, get_version_info, get_login_info, get_friend_list, get_group_list,
  get_group_info, get_group_member_info, get_stranger_info, get_msg, get_forward_msg,
  get_group_msg_history, get_friend_msg_history, get_recent_contact, get_group_honor_info,
  get_group_shut_list, get_essence_msg_list, get_group_at_all_remain, get_cookies,
  get_csrf_token, get_credentials, get_profile_like, get_unidirectional_friend_list
- 消息：send_like, mark_msg_as_read, set_essence_msg, delete_essence_msg,
  send_group_forward_msg, send_private_forward_msg, send_group_sign, set_group_sign
- 群管理：set_group_whole_ban, set_group_admin, set_group_card, set_group_leave,
  set_group_special_title, set_group_add_request, set_friend_add_request,
  set_group_anonymous, set_group_anonymous_ban, set_group_remark
- 文件：upload_group_file, upload_private_file, get_group_file_url, get_group_root_files,
  get_group_files_by_folder, get_group_file_system_info, create_group_file_folder,
  delete_group_file, delete_group_folder, move_group_file
- 账号/系统：set_self_longnick, set_online_status, set_input_status, set_restart,
  clean_cache, get_status"""

_TOOL_DESCRIPTION = f"""\
调用 OneBot 11 协议端的任意接口（GET/POST action）。本工具用于内置工具没有覆盖的能力；
内置工具已覆盖的操作请直接使用对应工具，不要用本工具重复实现：
- 回复/发送当前会话消息 → send_message（不要用 send_msg / send_group_msg / send_private_msg）
- 撤回消息 → recall_message（delete_msg）
- 群成员列表 → list_conversation_members（get_group_member_list）
- 踢人/禁言 → moderate_member（set_group_kick / set_group_ban）
- 修改群名 → set_group_name

{_ACTION_CATALOG}

返回值为协议端响应中的 data 字段；调用失败时返回 ok=false 与 error。"""


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _bounded_int(api: PluginAPI, key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(api.config.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _parse_params(raw: Any) -> dict[str, Any] | None:
    """兼容 JSON 对象字符串 / 直接的 dict / 留空。"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _blocked_actions(api: PluginAPI) -> set[str]:
    raw = api.config.get("blocked_actions")
    if not isinstance(raw, (list, tuple, set)):
        return set(DEFAULT_BLOCKED_ACTIONS)
    return {str(item).strip() for item in raw if str(item).strip()}


class OneBotApiPlugin:
    """把 OneBot 11 协议端接口暴露成一个通用工具。"""

    metadata = PluginMetadata(
        name="onebot_api",
        version="1.0.0",
        description="让模型自主调用 OneBot 11 协议端接口（内置工具已覆盖的除外）",
        author="baiyu-yu",
        homepage="https://github.com/baiyu-yu/sophos",
        default_config={
            "blocked_actions": DEFAULT_BLOCKED_ACTIONS,
            "timeout": 30,
            "max_result_chars": 12000,
        },
    )

    def setup(self, api: PluginAPI) -> None:
        @api.tool(
            name="onebot_call",
            description=_TOOL_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "OneBot 11 接口名，例如 get_group_list、send_like、upload_group_file",
                    },
                    "params": {
                        "type": "string",
                        "description": (
                            "该接口的原始参数，写成 JSON 对象字符串，例如 "
                            '{"group_id": 123456, "user_id": 10001, "card": "新昵称"}'
                        ),
                    },
                    "account_id": {
                        "type": "integer",
                        "description": "可选：指定用哪个已连接账号调用（Sophos 账号 ID）；不填用第一个已连接账号",
                    },
                    "reason": {
                        "type": "string",
                        "description": "可选：本次调用的目的，写入日志便于审计",
                    },
                },
                "required": ["action"],
            },
            group="plugin",
            category="output",
        )
        async def onebot_call(params: dict[str, Any], context: dict[str, Any]) -> Any:
            action = str(params.get("action") or "").strip()
            if not action:
                return {"ok": False, "action": "", "error": "action 不能为空"}

            blocked = _blocked_actions(api)
            if action in blocked:
                return {
                    "ok": False,
                    "action": action,
                    "error": f"action {action} 已被插件配置屏蔽（内置工具已覆盖，或可在插件配置里移除）",
                }

            call_params = _parse_params(params.get("params"))
            if call_params is None:
                return {
                    "ok": False,
                    "action": action,
                    "error": "params 必须是 JSON 对象字符串，例如 {\"group_id\": 123456}",
                }

            account_id = params.get("account_id")
            if account_id is not None:
                try:
                    account_id = int(account_id)
                except (TypeError, ValueError):
                    return {"ok": False, "action": action, "error": "account_id 必须是整数"}

            timeout = _bounded_int(api, "timeout", 30, 1, 120)
            limit = _bounded_int(api, "max_result_chars", 12000, 1000, 200000)
            reason = str(params.get("reason") or "").strip()
            api.logger.info(
                "onebot_call action=%s account=%s reason=%s params_keys=%s",
                action,
                account_id if account_id is not None else "-",
                reason or "-",
                sorted(call_params),
            )

            try:
                data = await api.protocol.call(
                    action,
                    call_params,
                    account_id=account_id,
                    timeout=float(timeout),
                )
            except Exception as exc:  # 协议端错误、超时、未连接都转成工具错误
                api.logger.warning("onebot_call 失败 action=%s params=%s: %s", action, call_params, exc)
                payload: dict[str, Any] = {
                    "ok": False,
                    "action": action,
                    "error": str(exc) or type(exc).__name__,
                    "params": call_params,
                }
                retcode = getattr(exc, "retcode", None)
                if retcode is not None:
                    payload["retcode"] = retcode
                    if retcode == 100:
                        payload["hint"] = (
                            "协议端认为参数无效（retcode=100）：请核对参数名与类型、目标是否在群内，"
                            "以及机器人是否有对应权限（如管理员才能改群名片）"
                        )
                return payload

            payload: dict[str, Any] = {"ok": True, "action": action, "data": data}
            text = _dump(payload)
            if len(text) > limit:
                return {
                    "ok": True,
                    "action": action,
                    "truncated": True,
                    "preview": text[:limit],
                    "hint": f"结果过长（{len(text)} 字符）已截断，请用更精确的参数缩小范围",
                }
            return payload

    def teardown(self) -> None:
        """无持久资源需要释放。"""


PLUGIN = OneBotApiPlugin()
