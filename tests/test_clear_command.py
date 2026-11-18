import unittest
from unittest.mock import AsyncMock, patch

from sophos.commands import CommandContext, handle_clear_command, handle_help_command
from sophos.platform import ConversationKind


def _context(cleared: int = 3) -> CommandContext:
    service = AsyncMock()
    service.store.clear_context.return_value = cleared
    return CommandContext(
        message_service=service,
        conversation_id=20,
        conversation_kind=ConversationKind.GROUP,
    )


def _sent_text(context: CommandContext) -> str:
    return context.message_service.send_message.await_args.args[0].text


class ClearCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_clears_assistant_messages_in_current_conversation(self) -> None:
        context = _context(5)

        handled = await handle_clear_command(
            ".clear assistant",
            context=context,
            pool=AsyncMock(),
            user_id=1,
            scope_type="conversation",
            scope_id=20,
        )

        self.assertTrue(handled)
        context.message_service.store.clear_context.assert_awaited_once_with(
            conversation_id=20,
            target="assistant",
        )
        self.assertIn("已清除当前会话的机器人消息: 5 条", _sent_text(context))

    async def test_clears_user_messages_everywhere_without_conversation_id(self) -> None:
        context = _context(9)

        with patch("sophos.commands.permission.is_master", return_value=True):
            await handle_clear_command(
                ".clear user global",
                context=context,
                pool=AsyncMock(),
                user_id=1,
                scope_type="conversation",
                scope_id=20,
            )

        context.message_service.store.clear_context.assert_awaited_once_with(
            conversation_id=None,
            target="user",
        )
        self.assertIn("已清除所有会话的用户消息: 9 条", _sent_text(context))

    async def test_global_clear_requires_master(self) -> None:
        context = _context()

        with patch("sophos.commands.permission.is_master", return_value=False):
            await handle_clear_command(
                ".clear all global",
                context=context,
                pool=AsyncMock(),
                user_id=1,
                scope_type="conversation",
                scope_id=20,
            )

        context.message_service.store.clear_context.assert_not_awaited()
        self.assertIn("Master", _sent_text(context))

    async def test_missing_target_prints_usage(self) -> None:
        context = _context()

        await handle_clear_command(
            ".clear",
            context=context,
            pool=AsyncMock(),
            user_id=1,
            scope_type="conversation",
            scope_id=20,
        )

        context.message_service.store.clear_context.assert_not_awaited()
        self.assertIn("用法: .clear assistant|user|all [global]", _sent_text(context))


class HelpCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_help_overview_lists_commands_with_one_line_intro(self) -> None:
        context = _context()

        with patch("sophos.commands.permission.is_master", return_value=True):
            await handle_help_command(
                ".help",
                context=context,
                pool=AsyncMock(),
                user_id=1,
                scope_type="conversation",
                scope_id=20,
            )

        text = _sent_text(context)
        self.assertIn("可用命令", text)
        self.assertIn(".clear", text)
        self.assertIn("清空上下文", text)
        # 总览不再输出多行用法说明
        self.assertNotIn("用法:", text)

    async def test_help_topic_returns_single_usage_line(self) -> None:
        context = _context()

        with patch("sophos.commands.permission.is_master", return_value=True):
            await handle_help_command(
                ".help clear",
                context=context,
                pool=AsyncMock(),
                user_id=1,
                scope_type="conversation",
                scope_id=20,
            )

        text = _sent_text(context)
        self.assertTrue(text.startswith(".clear — 清空上下文"))
        self.assertIn("用法: .clear assistant|user|all [global]", text)


if __name__ == "__main__":
    unittest.main()
