"""OneBot 11 通用接口调用插件。

让模型可以自主调用协议端（NapCat / Lagrange / go-cqhttp / LLOneBot 等）的任意
OneBot 11 接口。只默认屏蔽「会让消息绕过 Sophos 入库/权限链路」的写操作
（发消息、撤回、踢人、禁言），其余接口——尤其是查询类——都允许直接调用。

注意：actor 节点只挂输出类工具，`list_conversation_members` 之类的内置查询工具
在该节点并不可用，所以查询类接口必须允许本工具调用，否则模型查不到群号/成员。
群相关接口缺少 `group_id` 时会自动用当前会话的群号补全。

插件配置（WebUI 插件页 → 配置）：
  - blocked_actions: 禁止调用的 action 列表，默认只屏蔽绕过消息入库/权限的写操作
  - timeout:         单次调用超时秒数（1–120，默认 30）
  - max_result_chars: 返回结果最大字符数，超出截断（1000–200000，默认 12000）
"""

from __future__ import annotations

import json
from typing import Any

from sophos.platform import ConversationKind
from sophos.plugins import PluginAPI, PluginMetadata

# 只屏蔽会让消息绕过 Sophos 入库/权限链路的写操作；查询类接口一律放行。
DEFAULT_BLOCKED_ACTIONS = [
    "send_msg",
    "send_group_msg",
    "send_private_msg",
    "send_group_forward_msg",
    "send_private_forward_msg",
    "delete_msg",
    "set_group_kick",
    "set_group_ban",
]

# 被屏蔽时提示对应的内置工具，避免模型反复试错。
_BUILTIN_EQUIVALENTS = {
    "send_msg": "send_message",
    "send_group_msg": "send_message",
    "send_private_msg": "send_message",
    "send_group_forward_msg": "send_message",
    "send_private_forward_msg": "send_message",
    "delete_msg": "recall_message",
    "set_group_kick": "moderate_member(action=kick)",
    "set_group_ban": "moderate_member(action=ban)",
}

# 这些 action 需要 group_id；模型只知道自己所在会话，缺省时用当前群号补全。
_GROUP_SCOPED_ACTIONS = frozenset(
    {
        "get_group_info",
        "get_group_member_list",
        "get_group_member_info",
        "get_group_honor_info",
        "get_group_shut_list",
        "get_group_msg_history",
        "get_group_root_files",
        "get_group_files_by_folder",
        "get_group_file_url",
        "get_group_file_system_info",
        "get_group_at_all_remain",
        "set_group_card",
        "set_group_name",
        "set_group_kick",
        "set_group_ban",
        "set_group_whole_ban",
        "set_group_admin",
        "set_group_leave",
        "set_group_special_title",
        "set_group_add_request",
        "set_group_remark",
        "set_group_anonymous",
        "set_group_anonymous_ban",
        "set_group_sign",
        "upload_group_file",
        "create_group_file_folder",
        "delete_group_file",
        "delete_group_folder",
        "move_group_file",
        "get_essence_msg_list",
        "set_essence_msg",
        "delete_essence_msg",
    }
)

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
调用 OneBot 11 协议端的任意接口（GET/POST action）。查询类接口（群列表、群成员、群信息、
历史消息、文件列表等）都可以直接调用；只有会让消息绕过 Sophos 入库/权限的写操作被屏蔽：
- 回复/发送当前会话消息 → send_message（send_msg / send_group_msg / send_private_msg 被屏蔽）
- 撤回消息 → recall_message（delete_msg 被屏蔽）
- 踢人/禁言 → moderate_member（set_group_kick / set_group_ban 被屏蔽）
- 查询群成员 → 直接用本工具的 get_group_member_list（actor 节点没有内置查询工具）
- 修改群名片 → 直接用本工具的 set_group_card

需要 group_id 的接口如果在 params 里省略 group_id，会自动使用当前会话所在的群号，
所以通常只需传其余参数，例如 {{"user_id": 10001, "card": "新名片"}}。

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


def _blocked_message(action: str) -> str:
    equivalent = _BUILTIN_EQUIVALENTS.get(action)
    if equivalent:
        return (
            f"action {action} 已被插件屏蔽：请改用内置工具 {equivalent}"
            f"（避免绕过消息入库/权限校验）；如确需直接调用，可在插件配置 blocked_actions 中移除 {action}"
        )
    return f"action {action} 已被插件配置 blocked_actions 屏蔽；移除该项即可调用"


async def _current_group_id(api: PluginAPI, context: dict[str, Any]) -> int | None:
    """取当前会话对应的群号；私聊或查询失败时返回 None。"""
    conversation_id = context.get("conversation_id")
    service = api.runtime.message_service
    platform_store = getattr(service, "platform_store", None)
    if conversation_id is None or platform_store is None:
        return None
    try:
        conversation = await platform_store.get_conversation(int(conversation_id))
    except Exception:  # 查询失败不应该让工具调用本身失败
        return None
    if conversation is None or conversation.kind != ConversationKind.GROUP:
        return None
    try:
        return int(conversation.external_conversation_id)
    except (TypeError, ValueError):
        return None


class OneBotApiPlugin:
    """把 OneBot 11 协议端接口暴露成一个通用工具。"""

    metadata = PluginMetadata(
        name="onebot_api",
        version="1.1.0",
        description="让模型自主调用 OneBot 11 协议端接口（仅屏蔽绕过消息入库的写操作）",
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
                return {"ok": False, "action": action, "error": _blocked_message(action)}

            call_params = _parse_params(params.get("params"))
            if call_params is None:
                return {
                    "ok": False,
                    "action": action,
                    "error": "params 必须是 JSON 对象字符串，例如 {\"group_id\": 123456}",
                }

            if action in _GROUP_SCOPED_ACTIONS and not call_params.get("group_id"):
                group_id = await _current_group_id(api, context)
                if group_id is not None:
                    call_params["group_id"] = group_id
                    api.logger.info(
                        "onebot_call 自动补全 group_id=%s action=%s", group_id, action
                    )

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
