"""OneBot 11 通用接口调用插件（SnowLuma 动作目录版）。

让模型可以自主调用协议端（SnowLuma / NapCat / Lagrange / LLOneBot 等）的任意
OneBot 11 接口。插件内置 SnowLuma 官方动作目录（222 个 action、12 个分类），
用于：

* 校验 action 名并提供拼写建议（避免模型臆造接口）；
* ``onebot_api_docs`` 工具按关键词/分类/名称查询参数与示例；
* 按参数 ``role`` 自动补全 ``group_id``（当前群号）与 ``user_id``（内部 uid → 平台账号）。

只默认屏蔽「会让消息绕过 Sophos 入库/权限链路」的写操作（发消息、转发、撤回、
踢人、禁言、原始包），其余接口——尤其是查询类——都允许直接调用。

插件配置（WebUI 插件页 → 配置）：
  - blocked_actions:      禁止调用的 action 列表，默认只屏蔽绕过消息入库/权限的写操作
  - allow_unknown_actions: 允许调用目录中没有的 action（默认 false，避免拼错）
  - timeout:              单次调用超时秒数（1–120，默认 30）
  - max_result_chars:     返回结果最大字符数，超出截断（1000–200000，默认 12000）
"""

from __future__ import annotations

import difflib
import importlib.util
import json
from pathlib import Path
from typing import Any

from sophos.platform import ConversationKind
from sophos.plugins import PluginAPI, PluginMetadata


def _load_catalog() -> Any:
    """加载随插件分发的动作目录（目录安装用相对导入，单文件安装回退到同目录文件）。"""
    try:
        from . import actions as catalog  # type: ignore[import-not-found]

        return catalog
    except Exception:  # 单文件安装或缺少包上下文
        path = Path(__file__).with_name("actions.py")
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("sophos_onebot_actions", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


_catalog = _load_catalog()
ACTIONS: dict[str, dict[str, Any]] = dict(getattr(_catalog, "ACTIONS", {}) or {})
CATEGORIES: tuple[str, ...] = tuple(getattr(_catalog, "CATEGORIES", ()) or ())
CATEGORY_ACTIONS: dict[str, tuple[str, ...]] = dict(getattr(_catalog, "CATEGORY_ACTIONS", {}) or {})
CATALOG_SOURCE: str = str(getattr(_catalog, "CATALOG_SOURCE", "unknown"))
ALIASES: dict[str, str] = {
    str(alias): name for name, spec in ACTIONS.items() for alias in spec.get("aliases", ())
}

# 只屏蔽会让消息绕过 Sophos 入库/权限链路的写操作；查询类接口一律放行。
DEFAULT_BLOCKED_ACTIONS = [
    "send_msg",
    "send_group_msg",
    "send_private_msg",
    "send_group_forward_msg",
    "send_private_forward_msg",
    "send_forward_msg",
    "upload_forward_msg",
    "upload_foward_msg",
    "forward_group_single_msg",
    "forward_friend_single_msg",
    "send_flash_msg",
    "send_custom_face",
    "send_group_ai_record",
    "send_packet",
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
    "send_forward_msg": "send_message",
    "upload_forward_msg": "send_message",
    "upload_foward_msg": "send_message",
    "forward_group_single_msg": "send_message",
    "forward_friend_single_msg": "send_message",
    "send_flash_msg": "send_message",
    "send_custom_face": "send_image（发送表情图片）或 send_message",
    "delete_msg": "recall_message",
    "set_group_kick": "moderate_member(action=kick)",
    "set_group_ban": "moderate_member(action=ban)",
}

_PLACEHOLDER_BY_ROLE = {
    "group_id": "<当前群号，可省略>",
    "user_id": "<内部 uid，程序会自动映射成平台账号>",
    "member_id": "<内部 uid，程序会自动映射成平台账号>",
    "message_id": "<消息 ID>",
    "file_id": "<文件 ID>",
    "image": "<图片文件/URL>",
    "file": "<文件路径>",
    "record": "<语音文件>",
    "video": "<视频文件>",
    "face_id": "<表情 ID>",
    "timestamp": "<时间戳>",
    "duration": "<时长秒>",
}

_PLACEHOLDER_BY_TYPE = {
    "uint": 1,
    "int": 1,
    "number": 1,
    "string": "<文本>",
    "messageId": "<消息 ID>",
    "bool": True,
    "object": {},
    "raw": {},
    "enum": "<枚举值>",
    "string[]": ["<文本>"],
    "uint[]": [1],
    "message": [{"type": "text", "data": {"text": "<文本>"}}],
    "string | object[]": ["<文本>"],
}

_TOOL_DESCRIPTION = f"""\
调用 OneBot 11 协议端的任意接口（GET/POST action）。内置 SnowLuma 官方动作目录：
{CATALOG_SOURCE}，共 {len(ACTIONS) or "多"} 个 action、{len(CATEGORIES) or 12} 个分类
（{'、'.join(CATEGORIES) or '信息、消息、群信息、群管理、扩展…'}）。

不确定 action 名或参数时，先调用 onebot_api_docs：
- onebot_api_docs(keyword="公告")  → 按关键词搜索
- onebot_api_docs(category="群管理") → 列出某类动作
- onebot_api_docs(action="set_group_card") → 查看参数、是否只读与示例

常用直接调用：
- 查询群成员：get_group_member_list（actor 节点没有内置查询工具，直接用本工具）
- 查询群信息/群列表：get_group_info / get_group_list
- 改群名片：set_group_card，params 只需 user_id（填上下文里用户名后面的内部 uid）
- 群公告：_get_group_notice / _send_group_notice；精华：get_essence_msg_list
- 群文件：get_group_root_files / upload_group_file / get_group_file_url

参数规则：
- params 是一个 JSON 对象字符串，例如 {{"group_id": 123456, "user_id": 12}}
- 需要 group_id 的接口可省略，程序会自动填当前群号；user_id 内部 uid 会自动映射成 QQ 号
- 所以改群名片通常只需：{{"action": "set_group_card", "params": {{"user_id": 12, "card": "新名片"}}}}

仅以下写操作被屏蔽（会让消息绕过 Sophos 入库/权限）：发消息/转发 → send_message；
撤回 → recall_message；踢人/禁言 → moderate_member。需要时可在插件配置 blocked_actions 调整。

返回协议端响应中的 data 字段；失败返回 ok=false 与 error（含 retcode 与排查提示）。"""


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


def _allow_unknown(api: PluginAPI) -> bool:
    return bool(api.config.get("allow_unknown_actions", False))


def _blocked_message(action: str) -> str:
    equivalent = _BUILTIN_EQUIVALENTS.get(action)
    if equivalent:
        return (
            f"action {action} 已被插件屏蔽：请改用内置工具 {equivalent}"
            f"（避免绕过消息入库/权限校验）；如确需直接调用，可在插件配置 blocked_actions 中移除 {action}"
        )
    return f"action {action} 已被插件配置 blocked_actions 屏蔽；移除该项即可调用"


def _action_params(action: str) -> tuple[tuple[str, bool, str, str, str], ...]:
    return tuple(ACTIONS.get(action, {}).get("params", ()))


def _role_params(action: str, roles: set[str]) -> tuple[str, ...]:
    return tuple(param[0] for param in _action_params(action) if param[3] in roles)


def _resolve_action(action: str) -> str:
    return ALIASES.get(action, action)


def _suggest_actions(action: str, limit: int = 3) -> list[str]:
    if not ACTIONS:
        return []
    return difflib.get_close_matches(action, list(ACTIONS), n=limit, cutoff=0.55)


def _example_params(action: str) -> dict[str, Any]:
    example: dict[str, Any] = {}
    for name, required, type_name, role, _description in _action_params(action):
        if not required:
            continue
        placeholder = _PLACEHOLDER_BY_ROLE.get(role)
        if placeholder is None:
            placeholder = _PLACEHOLDER_BY_TYPE.get(type_name, "<值>")
        example[name] = placeholder
    return example


def _describe_action(action: str) -> dict[str, Any]:
    spec = ACTIONS.get(action)
    if spec is None:
        return {}
    params = []
    for name, required, type_name, role, description in spec.get("params", ()):
        item: dict[str, Any] = {
            "name": name,
            "required": required,
            "type": type_name or "any",
            "description": description,
        }
        if role:
            item["role"] = role
        params.append(item)
    payload: dict[str, Any] = {
        "ok": True,
        "source": CATALOG_SOURCE,
        "action": action,
        "category": spec.get("category", ""),
        "summary": spec.get("summary", ""),
        "read_only": bool(spec.get("read_only", False)),
        "blocked": action in DEFAULT_BLOCKED_ACTIONS,
        "params": params,
        "example": {"action": action, "params": _example_params(action)},
    }
    equivalent = _BUILTIN_EQUIVALENTS.get(action)
    if equivalent:
        payload["builtin_equivalent"] = equivalent
    aliases = tuple(spec.get("aliases") or ())
    if aliases:
        payload["aliases"] = list(aliases)
    return payload


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


async def _map_internal_user_id(
    api: PluginAPI, *, account_id: int | None, value: Any
) -> int | str | None:
    """把 Sophos 内部用户 ID 映射成协议端账号（QQ 号）；不认识的 ID 返回 None。"""
    service = api.runtime.message_service
    platform_store = getattr(service, "platform_store", None)
    if platform_store is None or account_id is None:
        return None
    try:
        internal_id = int(value)
    except (TypeError, ValueError):
        return None
    try:
        identity = await platform_store.get_identity_for_account(
            user_id=internal_id, account_id=int(account_id)
        )
    except Exception:  # 映射失败时按原值透传，让协议端报错
        return None
    if identity is None:
        return None
    external = str(identity.external_user_id)
    return int(external) if external.isdigit() else external


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == 0


class OneBotApiPlugin:
    """把 OneBot 11 协议端接口暴露成通用工具，并附带动作目录查询。"""

    metadata = PluginMetadata(
        name="onebot_api",
        version="1.3.0",
        description="让模型自主调用 OneBot 11 协议端接口（内置 SnowLuma 222 个动作目录）",
        author="baiyu-yu",
        homepage="https://github.com/baiyu-yu/sophos",
        default_config={
            "blocked_actions": DEFAULT_BLOCKED_ACTIONS,
            "allow_unknown_actions": False,
            "timeout": 30,
            "max_result_chars": 12000,
        },
    )

    def setup(self, api: PluginAPI) -> None:
        @api.tool(
            name="onebot_api_docs",
            description=(
                "查询 OneBot 动作文档（SnowLuma 目录）。不传参数列出分类；传 keyword 按关键词搜索；"
                "传 category 列出某类动作；传 action 查看该接口的说明、参数类型、是否只读与示例。"
                "调用 onebot_call 前不确定 action 名或参数时先用它，能避免拼错接口名。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "要查询的 action 名，例如 get_group_member_list",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "按关键词搜索 action 名与说明，例如 公告、文件、群名片",
                    },
                    "category": {
                        "type": "string",
                        "enum": list(CATEGORIES) or ["信息", "消息", "群信息", "群管理", "扩展"],
                        "description": "按分类过滤，例如 群管理、群文件、空间",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "description": "搜索时最多返回多少条，默认 20",
                    },
                },
            },
            group="plugin",
            category="input",
        )
        async def onebot_api_docs(params: dict[str, Any], context: dict[str, Any]) -> Any:
            if not ACTIONS:
                return {
                    "ok": False,
                    "error": "动作目录未随插件安装（缺少 actions.py），请以目录/zip 形式安装插件",
                }
            raw_action = str(params.get("action") or "").strip()
            if raw_action:
                action = _resolve_action(raw_action)
                payload = _describe_action(action)
                if payload:
                    return payload
                return {
                    "ok": False,
                    "action": raw_action,
                    "error": f"未知 action: {raw_action}",
                    "suggestions": _suggest_actions(raw_action),
                    "hint": "可以用 keyword 搜索，例如 onebot_api_docs(keyword=\"群成员\")",
                }

            raw_category = str(params.get("category") or "").strip()
            keyword = str(params.get("keyword") or "").strip()
            limit = params.get("limit")
            try:
                limit_value = max(1, min(60, int(limit))) if limit is not None else 20
            except (TypeError, ValueError):
                limit_value = 20

            if not keyword and not raw_category:
                counts = {name: len(CATEGORY_ACTIONS.get(name, ())) for name in CATEGORIES}
                samples = {
                    name: list(CATEGORY_ACTIONS.get(name, ())[:6]) for name in CATEGORIES
                }
                return {
                    "ok": True,
                    "source": CATALOG_SOURCE,
                    "total": len(ACTIONS),
                    "categories": counts,
                    "samples": samples,
                    "hint": (
                        "用 onebot_api_docs(keyword=\"关键词\") 搜索，"
                        "或 onebot_api_docs(action=\"接口名\") 查看参数"
                    ),
                }

            needle = keyword.lower()
            matches: list[dict[str, Any]] = []
            for name in sorted(ACTIONS):
                spec = ACTIONS[name]
                if raw_category and spec.get("category") != raw_category:
                    continue
                if needle and needle not in name.lower() and needle not in str(spec.get("summary", "")).lower():
                    continue
                matches.append(
                    {
                        "name": name,
                        "summary": spec.get("summary", ""),
                        "category": spec.get("category", ""),
                        "read_only": bool(spec.get("read_only", False)),
                        "blocked": name in DEFAULT_BLOCKED_ACTIONS,
                    }
                )

            payload = {
                "ok": True,
                "source": CATALOG_SOURCE,
                "total": len(matches),
                "returned": min(len(matches), limit_value),
                "actions": matches[:limit_value],
            }
            if len(matches) > limit_value:
                payload["hint"] = f"结果共 {len(matches)} 条，已截断；可用更精确的关键词或 category 过滤"
            if not matches:
                payload["suggestions"] = _suggest_actions(keyword or raw_category)
            return payload

        @api.tool(
            name="onebot_call",
            description=_TOOL_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "OneBot 11 接口名，例如 get_group_member_list、set_group_card、"
                            "upload_group_file；不确定时先用 onebot_api_docs 查询"
                        ),
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
            raw_action = str(params.get("action") or "").strip()
            if not raw_action:
                return {"ok": False, "action": "", "error": "action 不能为空"}

            action = _resolve_action(raw_action)
            if action != raw_action:
                api.logger.info("onebot_call action 别名 %s → %s", raw_action, action)
            if ACTIONS and action not in ACTIONS and not _allow_unknown(api):
                return {
                    "ok": False,
                    "action": raw_action,
                    "error": f"未知 action: {raw_action}（SnowLuma 目录中没有这个接口）",
                    "suggestions": _suggest_actions(action),
                    "hint": (
                        "用 onebot_api_docs(keyword=...) 搜索可用 action；"
                        "如果确实是协议端私有接口，可在插件配置中打开 allow_unknown_actions"
                    ),
                }

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

            account_id = params.get("account_id")
            if account_id is not None:
                try:
                    account_id = int(account_id)
                except (TypeError, ValueError):
                    return {"ok": False, "action": action, "error": "account_id 必须是整数"}
            else:
                accounts = api.protocol.accounts()
                account_id = accounts[0] if accounts else None

            # 按目录里的参数 role 自动补全：group_id 用当前群号，user_id/member_id 映射内部 uid。
            group_id: int | None = None
            group_id_loaded = False
            for name, _required, _type, role, _description in _action_params(action):
                if role == "group_id" and _is_missing(call_params.get(name)):
                    if not group_id_loaded:
                        group_id = await _current_group_id(api, context)
                        group_id_loaded = True
                    if group_id is not None:
                        call_params[name] = group_id
                        api.logger.info(
                            "onebot_call 自动补全 %s=%s action=%s", name, group_id, action
                        )
                elif role in {"user_id", "member_id"} and not _is_missing(call_params.get(name)):
                    raw_user_id = call_params[name]
                    mapped = await _map_internal_user_id(
                        api, account_id=account_id, value=raw_user_id
                    )
                    if mapped is not None and str(mapped) != str(raw_user_id):
                        api.logger.info(
                            "onebot_call 映射 %s 内部=%s → 平台=%s action=%s",
                            name,
                            raw_user_id,
                            mapped,
                            action,
                        )
                        call_params[name] = mapped

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
                            "以及机器人是否有对应权限（如管理员才能改群名片）；"
                            "可用 onebot_api_docs(action=...) 核对参数"
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
