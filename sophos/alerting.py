"""工作流失败聚合与 Master 告警。

单个失败只写日志和 runtime_errors；同一会话在时间窗口内累计到阈值后，
私信提醒所有 Master，避免在会话里打扰普通用户。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import asyncpg

from sophos import permission, runtime_config
from sophos.messaging import MessageService
from sophos.platform import ConversationKind, SendMessageRequest
from sophos.platform_store import PlatformStore

logger = logging.getLogger(__name__)

_WINDOW_KEY = "failure_alert_window_seconds"
_THRESHOLD_KEY = "failure_alert_threshold"
_COOLDOWN_KEY = "failure_alert_cooldown_seconds"

_WINDOW_SECONDS = 600.0
_THRESHOLD = 3
_COOLDOWN_SECONDS = 1800.0


@dataclass(slots=True)
class _FailureBucket:
    count: int = 0
    window_started: float = 0.0
    last_reason: str = ""
    notified_at: float = 0.0


_buckets: dict[int, _FailureBucket] = {}


def _number(key: str, default: float) -> float:
    try:
        value = float(runtime_config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def reset() -> None:
    """清空聚合状态（测试用）。"""
    _buckets.clear()


async def record_failure(
    *,
    pool: asyncpg.Pool,
    message_service: MessageService,
    platform_store: PlatformStore,
    conversation_id: int,
    reason: str,
) -> None:
    """累计一次会话失败；达到阈值时私信 Master。"""
    now = time.monotonic()
    window = _number(_WINDOW_KEY, _WINDOW_SECONDS)
    threshold = max(1, int(_number(_THRESHOLD_KEY, _THRESHOLD)))
    cooldown = _number(_COOLDOWN_KEY, _COOLDOWN_SECONDS)

    bucket = _buckets.get(conversation_id)
    if bucket is None or now - bucket.window_started > window:
        bucket = _FailureBucket(window_started=now)
        _buckets[conversation_id] = bucket

    bucket.count += 1
    bucket.last_reason = reason
    if bucket.count < threshold:
        return
    if bucket.notified_at and now - bucket.notified_at < cooldown:
        return

    bucket.notified_at = now
    count = bucket.count
    bucket.count = 0
    bucket.window_started = now
    try:
        sent = await _notify_masters(
            pool=pool,
            message_service=message_service,
            platform_store=platform_store,
            conversation_id=conversation_id,
            count=count,
            window_seconds=int(window),
            reason=reason,
        )
        logger.warning("会话 %s 连续失败 %d 次，已通知 %d 位 Master", conversation_id, count, sent)
    except Exception:
        logger.exception("发送 Master 失败告警失败 conversation=%s", conversation_id)


async def _notify_masters(
    *,
    pool: asyncpg.Pool,
    message_service: MessageService,
    platform_store: PlatformStore,
    conversation_id: int,
    count: int,
    window_seconds: int,
    reason: str,
) -> int:
    """向所有 Master 私信失败汇总，返回成功发送的数量。"""
    conversation = await platform_store.get_conversation(conversation_id)
    if conversation is None:
        logger.warning("无法定位告警会话 %s，跳过 Master 通知", conversation_id)
        return 0
    masters = await permission.list_masters(pool)
    if not masters:
        logger.warning("未配置任何 Master 用户，失败告警只写入日志：conversation=%s", conversation_id)
        return 0

    text = (
        "[Sophos 运行告警]\n"
        f"会话 #{conversation_id}（{conversation.display_name or conversation.kind.value}）"
        f"在最近 {max(1, window_seconds // 60)} 分钟内连续失败 {count} 次。\n"
        f"最近原因：{reason}\n"
        "请检查模型服务商、网络与权限配置；完整堆栈见 WebUI 日志页。"
    )
    sent = 0
    for master in masters:
        user_id = int(master["user_id"])  # type: ignore[arg-type]
        identity = await platform_store.get_identity_for_account(
            user_id=user_id,
            account_id=conversation.account_id,
        )
        if identity is None:
            logger.info("Master %s 在当前账号下没有身份，跳过告警私信", user_id)
            continue
        direct = await platform_store.resolve_conversation(
            account_id=conversation.account_id,
            kind=ConversationKind.DIRECT,
            external_conversation_id=identity.external_user_id,
            display_name=identity.display_name,
        )
        try:
            await message_service.send_message(
                SendMessageRequest(conversation_id=direct.conversation_id, text=text)
            )
            sent += 1
        except Exception:
            logger.exception("向 Master %s 发送失败告警失败", user_id)
    return sent
