"""Unified message delivery service used by agents, commands, and fallbacks."""

from __future__ import annotations

import logging

from sophos import observability
from sophos.adapter_router import AdapterRouter
from sophos.message_store import MessageStore
from sophos.platform import (
    AdapterSendRequest,
    Capability,
    CapabilityUnavailableError,
    SendMessageRequest,
    SentMessage,
)
from sophos.platform_store import PlatformStore

logger = logging.getLogger(__name__)

# 文本里出现换页符时拆成多条消息（多个气泡）；"\f" 不参与渲染。
TEXT_BUBBLE_SEPARATOR = "\f"


def split_text_bubbles(text: str) -> list[str]:
    """按 ``\\f`` 把文本拆成多条气泡；没有分隔符时原样返回单条。"""
    if not text:
        return []
    if TEXT_BUBBLE_SEPARATOR not in text:
        return [text]
    parts = [part.strip() for part in text.split(TEXT_BUBBLE_SEPARATOR)]
    return [part for part in parts if part] or [text]


class MessageService:
    def __init__(self, store: MessageStore, platform_store: PlatformStore, router: AdapterRouter):
        self.store = store
        self.platform_store = platform_store
        self.router = router

    async def send_message(self, request: SendMessageRequest) -> SentMessage:
        conversation = await self.platform_store.get_conversation(request.conversation_id)
        if conversation is None:
            raise ValueError(f"unknown conversation_id: {request.conversation_id}")
        adapter = self.router.for_account(conversation.account_id, Capability.MESSAGE_SEND)

        # 0 / 负数来自模型「不回复」的占位值，等价于不指定回复目标。
        reply_to_message_id = request.reply_to_message_id
        if reply_to_message_id is not None and int(reply_to_message_id) <= 0:
            reply_to_message_id = None

        parts = split_text_bubbles(request.text)
        if not parts and not request.inline_media:
            raise ValueError("message content cannot be empty")
        if not parts:
            parts = [""]

        sent: SentMessage | None = None
        for index, part in enumerate(parts):
            first = index == 0
            last = index == len(parts) - 1
            segments: list[dict] = []
            if first and reply_to_message_id is not None:
                self._require_optional_capability(adapter, Capability.MESSAGE_REPLY)
                locator = await self.store.get_delivery_locator(reply_to_message_id)
                if locator is None:
                    raise ValueError(
                        f"回复目标消息不存在或尚未成功送达: {reply_to_message_id}（请改用当前对话中已送达的消息 ID）"
                    )
                binding_id, reply_conversation_id, external_message_id = locator
                if binding_id != adapter.binding_id or reply_conversation_id != conversation.conversation_id:
                    raise ValueError("reply target belongs to another adapter binding or conversation")
                segments.append({"type": "reply", "data": {"external_message_id": external_message_id}})
            if first:
                for user_id in request.mention_user_ids:
                    self._require_optional_capability(adapter, Capability.MESSAGE_MENTION)
                    segments.append({"type": "mention", "data": {"user_id": user_id}})
            if part:
                segments.append({"type": "text", "data": {"text": part}})
            if last:
                if request.attachment_ids:
                    self._require_optional_capability(adapter, Capability.MESSAGE_ATTACHMENT)
                    raise ValueError("attachment materialization is not implemented")
                if request.inline_media:
                    self._require_optional_capability(adapter, Capability.MESSAGE_IMAGE)
                segments.extend(request.inline_media)
            sent = await self._deliver(
                conversation=conversation,
                adapter=adapter,
                segments=segments,
                reply_to_message_id=reply_to_message_id if first else None,
                metadata=request.metadata,
            )
        assert sent is not None
        return sent

    async def _deliver(
        self,
        *,
        conversation,
        adapter,
        segments: list[dict],
        reply_to_message_id: int | None,
        metadata: dict | None,
    ) -> SentMessage:
        try:
            delivered = await adapter.send_message(AdapterSendRequest(conversation=conversation, segments=segments))
        except Exception as exc:
            with observability.scope(conversation_id=conversation.conversation_id):
                await observability.record_error("send_message", exc)
            raise
        observability.message_sent(conversation.conversation_id)
        internal_id = await self.store.save_outbound_message(
            adapter_binding_id=adapter.binding_id,
            conversation_id=conversation.conversation_id,
            sender_identity_id=adapter.self_identity.identity_id,
            external_message_id=delivered.external_message_id,
            segments=segments,
            reply_to_message_id=reply_to_message_id,
            occurred_at=delivered.occurred_at,
            metadata=metadata,
            raw_payload=delivered.raw_payload,
        )
        logger.info(
            "已发送消息 conversation=%s internal_id=%s external_id=%s reply_to=%s",
            conversation.conversation_id,
            internal_id,
            delivered.external_message_id,
            reply_to_message_id,
        )
        return SentMessage(
            message_id=internal_id,
            conversation_id=conversation.conversation_id,
            external_message_id=delivered.external_message_id,
        )

    @staticmethod
    def _require_optional_capability(adapter: object, capability: Capability) -> None:
        capabilities = getattr(adapter, "capabilities", frozenset())
        if capability not in capabilities:
            binding_id = getattr(adapter, "binding_id", "unknown")
            raise CapabilityUnavailableError(
                f"adapter binding {binding_id} does not support {capability.value}"
            )

    async def recall_message(self, message_id: int) -> None:
        locator = await self.store.get_delivery_locator(message_id)
        if locator is None:
            raise ValueError(f"unknown or undelivered message_id: {message_id}")
        binding_id, conversation_id, external_message_id = locator
        conversation = await self.platform_store.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"unknown conversation_id: {conversation_id}")
        adapter = self.router.for_binding(binding_id, Capability.MESSAGE_RECALL)
        await adapter.recall_message(conversation, external_message_id)
