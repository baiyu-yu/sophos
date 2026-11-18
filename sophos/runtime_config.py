"""运行时配置管理。

DB-backed KV 配置，支持热修改。启动时从 DB 加载到内存缓存，
写入时 UPSERT DB + 刷新缓存。.env 值仅作为初始默认值。

所有可调项都登记在 ``_SPECS`` 中：类型、分组、说明与校验规则由 WebUI 读取，
因此在 WebUI「设置」页可以修改任何运行时可调项，不需要改 .env 或重启。
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from sophos.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfigSpec:
    """一个可在 WebUI 编辑的配置项。"""

    key: str
    type: str  # str | int | float | bool | json | float?
    label: str
    group: str
    description: str = ""
    minimum: float | None = None
    maximum: float | None = None
    options: tuple[str, ...] = ()
    requires_restart: bool = False
    secret: bool = False


_GROUPS = (
    "身份与时间",
    "对话与上下文",
    "命令与触发",
    "模型参数",
    "视觉",
    "失败告警",
    "联网",
    "工作流",
    "数据清理",
    "日志与网络",
)


def _spec(
    key: str,
    type_: str,
    label: str,
    group: str,
    description: str = "",
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    options: tuple[str, ...] = (),
    requires_restart: bool = False,
    secret: bool = False,
) -> ConfigSpec:
    return ConfigSpec(
        key=key,
        type=type_,
        label=label,
        group=group,
        description=description,
        minimum=minimum,
        maximum=maximum,
        options=options,
        requires_restart=requires_restart,
        secret=secret,
    )


_SPECS: dict[str, ConfigSpec] = {
    spec.key: spec
    for spec in (
        _spec(
            "bot_id", "int", "机器人 QQ 号", "身份与时间", "登录的机器人账号；留空时使用协议端返回的账号。", minimum=0
        ),
        _spec("bot_nickname", "str", "机器人昵称", "身份与时间", "用于被 @ / 提及判断与提示词里的 {{nickname}}。"),
        _spec("timezone", "str", "时区", "身份与时间", "IANA 时区名，如 Asia/Shanghai；影响日志与 LLM 上下文时间。"),
        _spec(
            "max_context_messages",
            "int",
            "上下文消息条数",
            "对话与上下文",
            "每个会话最多带入 LLM 的历史消息条数。",
            minimum=1,
            maximum=1000,
        ),
        _spec(
            "include_co_account_in_context",
            "bool",
            "包含同账号其他消息",
            "对话与上下文",
            "把同账号下其他 bot / 手动发送的消息也纳入上下文。",
        ),
        _spec(
            "cross_context_mode",
            "str",
            "跨上下文注入",
            "对话与上下文",
            "背景注入方式。",
            options=("system", "inline", "off"),
        ),
        _spec("recent_global_limit", "int", "全局最近消息条数", "对话与上下文", minimum=0, maximum=500),
        _spec("recent_global_min_self", "int", "全局消息最少自身条数", "对话与上下文", minimum=0, maximum=200),
        _spec(
            "reply_max_length",
            "int",
            "回复长度上限",
            "对话与上下文",
            "单条回复的最大字符数（超出会截断）。",
            minimum=10,
            maximum=20000,
        ),
        _spec("forward_head_count", "int", "合并转发头部条数", "对话与上下文", minimum=0, maximum=20),
        _spec("forward_tail_count", "int", "合并转发尾部条数", "对话与上下文", minimum=0, maximum=20),
        _spec("forward_max_depth", "int", "合并转发最大深度", "对话与上下文", minimum=1, maximum=10),
        _spec("command_prefix", "str", "命令前缀", "命令与触发", "聊天里触发命令的前缀，1–3 个字符；不填写时默认 .。"),
        _spec(
            "trigger_regexes",
            "json",
            "触发正则",
            "命令与触发",
            "群聊消息匹配任意一条正则即触发回复，每行一条，最多 50 条。",
        ),
        _spec(
            "trigger_delay",
            "float",
            "触发延迟（秒）",
            "命令与触发",
            "收到消息后等待多久再判断是否回复。",
            minimum=0.0,
            maximum=600.0,
        ),
        _spec("trigger_qps", "float", "触发判断速率", "命令与触发", minimum=0.01, maximum=1000.0),
        _spec("trigger_wait_timeout", "float", "触发等待超时（秒）", "命令与触发", minimum=1.0, maximum=600.0),
        _spec("trigger_eval_context_limit", "int", "触发判断上下文条数", "命令与触发", minimum=1, maximum=200),
        _spec("trigger_eval_max_tokens", "int", "触发判断最大 token", "命令与触发", minimum=8, maximum=4096),
        _spec("trigger_eval_temperature", "float", "触发判断温度", "命令与触发", minimum=0.0, maximum=2.0),
        _spec("trigger_eval_image_wait", "float", "触发判断图片等待（秒）", "命令与触发", minimum=0.0, maximum=60.0),
        _spec("trigger_memory_limit", "int", "触发判断记忆条数", "命令与触发", minimum=0, maximum=20),
        _spec("trigger_memory_min_score", "float", "触发记忆最低分数", "命令与触发", minimum=0.0, maximum=1.0),
        _spec("trigger_bucket_capacity", "int", "令牌桶容量", "命令与触发", minimum=1, maximum=1000),
        _spec("trigger_bucket_refill", "float", "令牌桶补充速率", "命令与触发", minimum=0.1, maximum=1000.0),
        _spec(
            "llm_temperature",
            "float?",
            "生成温度",
            "模型参数",
            "留空表示不传，由服务商使用自身默认值。",
            minimum=0.0,
            maximum=2.0,
        ),
        _spec("llm_max_tokens", "int", "最大生成 token", "模型参数", minimum=1, maximum=200000),
        _spec("llm_max_tool_rounds", "int", "工具调用最大轮次", "模型参数", minimum=1, maximum=200),
        _spec(
            "llm_flatten_context",
            "bool",
            "拍平上下文",
            "模型参数",
            "把多轮消息合并成单条 user message，兼容不支持连续 user message 的模型。",
        ),
        _spec(
            "llm_user_schema",
            "str",
            "用户消息模板",
            "模型参数",
            "可用占位符：{{time}} {{mid}} {{name}} {{uid}} {{message}}；必须包含 {{message}}。",
        ),
        _spec("llm_bot_schema", "str", "Bot 消息模板", "模型参数", "拍平模式下使用；必须包含 {{message}}。"),
        _spec("vision_context_messages", "int", "图片识别上下文条数", "视觉", minimum=0, maximum=50),
        _spec("vision_max_tokens", "int", "图片识别最大 token", "视觉", minimum=16, maximum=100000),
        _spec("vision_defer_seconds", "float", "图片延迟识别（秒）", "视觉", minimum=0.0, maximum=3600.0),
        _spec("vision_generation_timeout", "float", "图片识别超时（秒）", "视觉", minimum=1.0, maximum=3600.0),
        _spec("vision_attempts", "int", "图片识别尝试次数", "视觉", minimum=1, maximum=10),
        _spec("vision_epsilon_init", "float", "ε-greedy 初始探索率", "视觉", minimum=0.0, maximum=1.0),
        _spec("vision_epsilon_min", "float", "ε-greedy 最低探索率", "视觉", minimum=0.0, maximum=1.0),
        _spec("vision_epsilon_decay", "float", "ε-greedy 衰减系数", "视觉", minimum=0.0, maximum=1.0),
        _spec(
            "vision_hash_size",
            "int",
            "图片哈希尺寸",
            "视觉",
            "imagehash average_hash 的 hash_size。",
            minimum=1,
            maximum=64,
        ),
        _spec(
            "failure_alert_threshold",
            "int",
            "失败告警阈值",
            "失败告警",
            "同一会话窗口内失败多少次后私信 Master。",
            minimum=1,
            maximum=100,
        ),
        _spec("failure_alert_window_seconds", "int", "失败告警窗口（秒）", "失败告警", minimum=10, maximum=86400),
        _spec("failure_alert_cooldown_seconds", "int", "失败告警冷却（秒）", "失败告警", minimum=0, maximum=86400),
        _spec("tavily_api_key", "str", "Tavily API Key", "联网", "留空则隐藏联网搜索工具。", secret=True),
        _spec("tavily_max_results", "int", "联网搜索条数", "联网", minimum=1, maximum=20),
        _spec("tavily_include_answer", "bool", "联网搜索返回摘要", "联网"),
        _spec(
            "agent_workflow",
            "json",
            "工作流定义",
            "工作流",
            "留空使用内置 collector/actor 工作流；一般请在「工作流」页编辑。",
        ),
        _spec("cleanup_messages_max_bytes", "int", "消息清理阈值（字节）", "数据清理", minimum=1000000, maximum=10**12),
        _spec("cleanup_memories_max_bytes", "int", "记忆清理阈值（字节）", "数据清理", minimum=1000000, maximum=10**12),
        _spec("cleanup_interval_seconds", "int", "清理间隔（秒）", "数据清理", minimum=60, maximum=86400),
        _spec(
            "log_max_bytes",
            "int",
            "日志文件大小上限",
            "日志与网络",
            "修改后需重启生效。",
            minimum=1024,
            maximum=10**10,
            requires_restart=True,
        ),
        _spec(
            "log_backup_count",
            "int",
            "日志备份数量",
            "日志与网络",
            "修改后需重启生效。",
            minimum=1,
            maximum=100,
            requires_restart=True,
        ),
    )
}

DEFAULT_USER_SCHEMA = "[{{time}}] #{{mid}} {{name}}({{uid}})：{{message}}"
DEFAULT_BOT_SCHEMA = "[{{time}}] #{{mid}} {{name}}：{{message}}"

_SCHEMA_DEFAULTS: dict[str, str] = {
    "llm_user_schema": DEFAULT_USER_SCHEMA,
    "llm_bot_schema": DEFAULT_BOT_SCHEMA,
}


def _coerce_schema(key: str, value: Any) -> Any:
    """模板缺少 {{message}}（常见于 .env 被行内 # 注释截断）时回退到内置默认。"""
    if key not in _SCHEMA_DEFAULTS:
        return value
    if isinstance(value, str) and "{{message}}" in value:
        return value
    return _SCHEMA_DEFAULTS[key]


def _default_schema(key: str, configured: Any) -> str:
    fallback = _SCHEMA_DEFAULTS[key]
    if isinstance(configured, str) and "{{message}}" in configured:
        return configured
    if isinstance(configured, str) and configured.strip():
        logger.warning(
            "配置 %s 的 .env 默认值 %r 缺少 {{message}}（疑似被行内 # 注释截断），"
            "已改用内置默认值；请在 WebUI「设置」中修正，或给 .env 里的值加引号",
            key,
            configured,
        )
    return fallback


_DEFAULTS: dict[str, Any] = {
    "bot_id": settings.bot_id,
    "bot_nickname": settings.bot_nickname,
    "timezone": settings.timezone,
    "max_context_messages": settings.max_context_messages,
    "include_co_account_in_context": settings.include_co_account_in_context,
    "cross_context_mode": settings.cross_context_mode,
    "recent_global_limit": 50,
    "recent_global_min_self": 5,
    "reply_max_length": 100,
    "forward_head_count": 3,
    "forward_tail_count": 2,
    "forward_max_depth": 2,
    "command_prefix": ".",
    "trigger_regexes": [],
    "trigger_delay": 2.0,
    "trigger_qps": 0.5,
    "trigger_wait_timeout": 30.0,
    "trigger_eval_context_limit": 20,
    "trigger_eval_max_tokens": 64,
    "trigger_eval_temperature": 0.0,
    "trigger_eval_image_wait": 8.0,
    "trigger_memory_limit": 3,
    "trigger_memory_min_score": 0.6,
    "trigger_bucket_capacity": 10,
    "trigger_bucket_refill": 6.0,
    "llm_temperature": settings.llm_temperature,
    "llm_max_tokens": settings.llm_max_tokens,
    "llm_max_tool_rounds": settings.llm_max_tool_rounds,
    "llm_flatten_context": settings.llm_flatten_context,
    "llm_user_schema": _default_schema("llm_user_schema", settings.llm_user_schema),
    "llm_bot_schema": _default_schema("llm_bot_schema", settings.llm_bot_schema),
    "vision_context_messages": 5,
    "vision_max_tokens": 1024,
    "vision_defer_seconds": 30.0,
    "vision_generation_timeout": 60.0,
    "vision_attempts": 2,
    "vision_epsilon_init": settings.vision_epsilon_init,
    "vision_epsilon_min": settings.vision_epsilon_min,
    "vision_epsilon_decay": settings.vision_epsilon_decay,
    "vision_hash_size": settings.vision_hash_size,
    "failure_alert_threshold": 3,
    "failure_alert_window_seconds": 600,
    "failure_alert_cooldown_seconds": 1800,
    "tavily_api_key": "",
    "tavily_max_results": 5,
    "tavily_include_answer": True,
    "agent_workflow": None,
    "cleanup_messages_max_bytes": 2 * 1024 * 1024 * 1024,
    "cleanup_memories_max_bytes": 2 * 1024 * 1024 * 1024,
    "cleanup_interval_seconds": 3600,
    "log_max_bytes": settings.log_max_bytes,
    "log_backup_count": settings.log_backup_count,
}

# spec 与 defaults 必须一一对应，启动时就暴露漏登记问题
_missing = set(_DEFAULTS) - set(_SPECS)
if _missing:  # pragma: no cover - 开发期保护
    raise RuntimeError(f"runtime config keys missing specs: {sorted(_missing)}")

_MAX_COMMAND_PREFIX_LENGTH = 3
_MAX_REGEX_COUNT = 50
_MAX_REGEX_LENGTH = 200


def _validate_command_prefix(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("命令前缀必须是字符串")
    prefix = value.strip()
    if not prefix:
        raise ValueError("命令前缀不能为空")
    if len(prefix) > _MAX_COMMAND_PREFIX_LENGTH:
        raise ValueError(f"命令前缀最多 {_MAX_COMMAND_PREFIX_LENGTH} 个字符")
    if any(char.isspace() for char in prefix):
        raise ValueError("命令前缀不能包含空白字符")
    return prefix


def _validate_trigger_regexes(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("触发正则必须是字符串数组")
    patterns: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("触发正则必须是字符串数组")
        pattern = item.strip()
        if not pattern:
            continue
        if len(pattern) > _MAX_REGEX_LENGTH:
            raise ValueError(f"单条正则最多 {_MAX_REGEX_LENGTH} 个字符: {pattern[:30]}…")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"正则无效: {pattern}（{exc}）") from exc
        patterns.append(pattern)
    if len(patterns) > _MAX_REGEX_COUNT:
        raise ValueError(f"最多配置 {_MAX_REGEX_COUNT} 条触发正则")
    return patterns


def _validate_timezone(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("时区必须是字符串")
    name = value.strip()
    try:
        ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001 - ZoneInfo 抛多种异常
        raise ValueError(f"无效的 IANA 时区: {name}") from exc
    return name


def _validate_schema(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("消息模板不能为空")
    if "{{message}}" not in value:
        raise ValueError("消息模板必须包含 {{message}} 占位符，否则上下文里会丢失正文")
    return value


_CUSTOM_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "command_prefix": _validate_command_prefix,
    "trigger_regexes": _validate_trigger_regexes,
    "timezone": _validate_timezone,
    "llm_user_schema": _validate_schema,
    "llm_bot_schema": _validate_schema,
}


def validate_value(key: str, value: Any) -> Any:
    """按 spec 校验并规范化一个配置值；非法时抛 ValueError。"""
    spec = _SPECS.get(key)
    if spec is None:
        raise ValueError(f"未知配置项: {key}")
    custom = _CUSTOM_VALIDATORS.get(key)
    if custom is not None:
        return custom(value)

    type_ = spec.type
    if type_ == "float?" and value is None:
        return None
    if type_ == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{spec.label} 必须是布尔值")
        return value
    if type_ in ("int", "float", "float?"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{spec.label} 必须是数字")
        if type_ == "int":
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(f"{spec.label} 必须是整数")
            value = int(value)
        else:
            value = float(value)
        if spec.minimum is not None and value < spec.minimum:
            raise ValueError(f"{spec.label} 不能小于 {spec.minimum:g}")
        if spec.maximum is not None and value > spec.maximum:
            raise ValueError(f"{spec.label} 不能大于 {spec.maximum:g}")
        return value
    if type_ == "str":
        if not isinstance(value, str):
            raise ValueError(f"{spec.label} 必须是字符串")
        if spec.options and value not in spec.options:
            raise ValueError(f"{spec.label} 只能是 {' / '.join(spec.options)}")
        return value
    if type_ == "json":
        try:
            return json.loads(json.dumps(value, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spec.label} 必须是合法的 JSON 值") from exc
    raise ValueError(f"未知配置类型: {type_}")


def list_specs() -> list[dict[str, Any]]:
    """返回全部配置项的元信息（供 WebUI 渲染表单）。"""
    items: list[dict[str, Any]] = []
    for spec in _SPECS.values():
        items.append(
            {
                "key": spec.key,
                "type": spec.type,
                "label": spec.label,
                "group": spec.group,
                "description": spec.description,
                "default": _DEFAULTS.get(spec.key),
                "minimum": spec.minimum,
                "maximum": spec.maximum,
                "options": list(spec.options),
                "requires_restart": spec.requires_restart,
                "secret": spec.secret,
            }
        )
    return items


def group_order() -> list[str]:
    """配置分组展示顺序。"""
    return list(_GROUPS)


_cache: dict[str, Any] = {}
_pool: asyncpg.Pool | None = None


async def init(pool: asyncpg.Pool) -> None:
    """启动时从 DB 加载全部配置到缓存。"""
    global _pool
    _pool = pool
    rows = await pool.fetch("SELECT key, value FROM bot_config")
    for row in rows:
        _cache[row["key"]] = json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
    # 旧版本可能把被截断的模板写进了数据库，这里静默回退到内置默认值
    for key in _SCHEMA_DEFAULTS:
        if key in _cache and _coerce_schema(key, _cache[key]) != _cache[key]:
            logger.warning("数据库中的 %s=%r 缺少 {{message}}，已回退内置默认模板", key, _cache[key])
            _cache.pop(key)
    logger.info("RuntimeConfig loaded %d keys from DB", len(_cache))


def get(key: str, default: Any = None) -> Any:
    """读取配置值。优先缓存 → _DEFAULTS → default。"""
    if key in _cache:
        return _coerce_schema(key, _cache[key])
    if key in _DEFAULTS:
        return _DEFAULTS[key]
    return default


async def set_value(key: str, value: Any) -> None:
    """写入配置值。UPSERT DB + 刷新缓存。"""
    if _pool is None:
        raise RuntimeError("RuntimeConfig not initialized")
    value_json = json.dumps(value, ensure_ascii=False)
    await _pool.execute(
        """
        INSERT INTO bot_config (key, value) VALUES ($1, $2::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        key,
        value_json,
    )
    _cache[key] = value
    logger.info("RuntimeConfig set %s = %r", key, value)


async def delete(key: str) -> bool:
    """删除配置值，恢复为 .env 默认。返回是否存在。"""
    if _pool is None:
        raise RuntimeError("RuntimeConfig not initialized")
    result = await _pool.execute("DELETE FROM bot_config WHERE key = $1", key)
    existed = result == "DELETE 1"
    _cache.pop(key, None)
    if existed:
        logger.info("RuntimeConfig reset %s to default", key)
    return existed


def get_all() -> dict[str, Any]:
    """返回所有可调配置的当前值（合并 defaults + cache）。"""
    merged = dict(_DEFAULTS)
    merged.update(_cache)
    for key in _SCHEMA_DEFAULTS:
        merged[key] = _coerce_schema(key, merged[key])
    return merged


def get_defaults() -> dict[str, Any]:
    """返回所有默认值。"""
    return dict(_DEFAULTS)


__all__ = [
    "ConfigSpec",
    "delete",
    "get",
    "get_all",
    "get_defaults",
    "group_order",
    "init",
    "list_specs",
    "set_value",
    "validate_value",
]
