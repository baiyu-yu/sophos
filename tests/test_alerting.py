import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sophos import alerting, runtime_config
from sophos.platform import ConversationKind

_ALERT_KEYS = (
    "failure_alert_threshold",
    "failure_alert_window_seconds",
    "failure_alert_cooldown_seconds",
)


class AlertingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        alerting.reset()
        runtime_config._cache["failure_alert_threshold"] = 2
        runtime_config._cache["failure_alert_window_seconds"] = 600
        runtime_config._cache["failure_alert_cooldown_seconds"] = 0.001

    def tearDown(self) -> None:
        alerting.reset()
        for key in _ALERT_KEYS:
            runtime_config._cache.pop(key, None)

    async def test_alert_fires_once_after_threshold(self) -> None:
        message_service = SimpleNamespace(send_message=AsyncMock())
        notify = AsyncMock(return_value=1)
        with patch.object(alerting, "_notify_masters", notify):
            for _ in range(3):
                await alerting.record_failure(
                    pool=object(),  # type: ignore[arg-type]
                    message_service=message_service,  # type: ignore[arg-type]
                    platform_store=SimpleNamespace(),  # type: ignore[arg-type]
                    conversation_id=9,
                    reason="boom",
                )

        self.assertEqual(notify.await_count, 1)
        self.assertEqual(notify.await_args.kwargs["count"], 2)

    async def test_cooldown_suppresses_repeated_alerts(self) -> None:
        runtime_config._cache["failure_alert_cooldown_seconds"] = 3600
        runtime_config._cache["failure_alert_threshold"] = 1
        notify = AsyncMock(return_value=1)
        with patch.object(alerting, "_notify_masters", notify):
            for _ in range(3):
                await alerting.record_failure(
                    pool=object(),  # type: ignore[arg-type]
                    message_service=SimpleNamespace(send_message=AsyncMock()),  # type: ignore[arg-type]
                    platform_store=SimpleNamespace(),  # type: ignore[arg-type]
                    conversation_id=9,
                    reason="boom",
                )

        self.assertEqual(notify.await_count, 1)

    async def test_notify_masters_sends_direct_message(self) -> None:
        conversation = SimpleNamespace(
            conversation_id=9,
            account_id=1,
            display_name="测试群",
            kind=ConversationKind.GROUP,
        )
        identity = SimpleNamespace(external_user_id="10001", display_name="Master")
        direct = SimpleNamespace(conversation_id=77)
        platform_store = SimpleNamespace(
            get_conversation=AsyncMock(return_value=conversation),
            get_identity_for_account=AsyncMock(return_value=identity),
            resolve_conversation=AsyncMock(return_value=direct),
        )
        message_service = SimpleNamespace(send_message=AsyncMock())

        with patch.object(alerting.permission, "list_masters", AsyncMock(return_value=[{"user_id": 5}])):
            sent = await alerting._notify_masters(
                pool=object(),  # type: ignore[arg-type]
                message_service=message_service,  # type: ignore[arg-type]
                platform_store=platform_store,  # type: ignore[arg-type]
                conversation_id=9,
                count=3,
                window_seconds=600,
                reason="LLMNodeExecutionError: boom",
            )

        self.assertEqual(sent, 1)
        request = message_service.send_message.await_args.args[0]
        self.assertEqual(request.conversation_id, 77)
        self.assertIn("连续失败 3 次", request.text)

    async def test_no_masters_skips_notification(self) -> None:
        platform_store = SimpleNamespace(
            get_conversation=AsyncMock(return_value=SimpleNamespace(conversation_id=9, account_id=1))
        )
        message_service = SimpleNamespace(send_message=AsyncMock())

        with patch.object(alerting.permission, "list_masters", AsyncMock(return_value=[])):
            sent = await alerting._notify_masters(
                pool=object(),  # type: ignore[arg-type]
                message_service=message_service,  # type: ignore[arg-type]
                platform_store=platform_store,  # type: ignore[arg-type]
                conversation_id=9,
                count=3,
                window_seconds=600,
                reason="boom",
            )

        self.assertEqual(sent, 0)
        message_service.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
