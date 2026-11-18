"""Sophos — Application entry point."""

import asyncio
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import web

from sophos import observability, permission, prompts, runtime_config
from sophos.adapter_router import AdapterRouter
from sophos.api import create_app
from sophos.cleanup import run_cleanup_loop
from sophos.config import settings
from sophos.connections import OneBotConnectionManager
from sophos.db import close_db, init_db
from sophos.llm.provider_manager import ProviderManager
from sophos.memory.store import MemoryStore
from sophos.message_store import MessageStore
from sophos.messaging import MessageService
from sophos.pipeline import INGEST_STAGES, RESPONSE_STAGES, Pipeline, PipelineContext
from sophos.platform import PlatformAdapter
from sophos.platform_store import PlatformStore
from sophos.plugins import DbPluginStateStore, PluginManager
from sophos.toolkit import runtime as tool_runtime

logger = logging.getLogger("sophos")

_ingest = Pipeline(INGEST_STAGES)
_response = Pipeline(RESPONSE_STAGES)

_LOG_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class _TzFormatter(logging.Formatter):
    """用配置时区替代本地时间的 Formatter。"""

    def __init__(self, fmt: str, tz: ZoneInfo) -> None:
        super().__init__(fmt)
        self._tz = tz

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"


def _log_preview(text: str, limit: int = 200) -> str:
    """Collapse a message body into one log-friendly line."""
    collapsed = " ".join((text or "").split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}…"


def _describe_message(message: Any) -> str:
    """Summarise message content for the received-message log line."""
    if _log_preview(message.plain_text):
        return _log_preview(message.plain_text)
    kinds = sorted({str(segment.get("type", "unknown")) for segment in message.segments})
    return f"[非文本消息: {', '.join(kinds)}]" if kinds else "[空消息]"


async def handle_event(
    adapter: PlatformAdapter,
    event: dict[str, Any],
    message_service: MessageService,
    store: MessageStore,
    provider_mgr: ProviderManager,
    session: aiohttp.ClientSession,
    memory_store: MemoryStore | None = None,
) -> None:
    """Normalize and process one platform event through the core pipeline."""
    message = await adapter.normalize_event(event)
    if message is None:
        return
    logger.info(
        "收到消息 conversation=%s(%s) account=%s sender=%s(%s) message=%s content=%s",
        message.conversation.conversation_id,
        message.conversation.kind.value,
        message.account_id,
        message.sender.display_name or message.sender.external_user_id,
        message.sender.external_user_id,
        message.external_message_id,
        _describe_message(message),
    )
    ctx = PipelineContext.from_event(message, adapter, message_service, store, provider_mgr, session)
    if memory_store is not None:
        ctx.state["memory_store"] = memory_store
    with observability.scope(conversation_id=ctx.conversation_id):
        await _ingest.run(ctx)
        await _response.run(ctx)


async def start() -> None:
    """Boot the application."""
    logger.info("Sophos is starting...")

    # 初始化数据库（建表 + 连接池）
    pool = await init_db()
    await observability.init(pool)
    store = MessageStore(pool)
    platform_store = PlatformStore(pool)
    router = AdapterRouter()
    message_service = MessageService(store, platform_store, router)
    interrupted = await store.fail_interrupted_enrichments()
    if interrupted:
        logger.warning("Marked %d interrupted enrichment message(s) as failed", interrupted)

    # 初始化运行时配置
    await runtime_config.init(pool)
    _configure_file_logging()
    await prompts.init(pool)
    await permission.init(pool)

    # 初始化 LLM provider 管理器
    provider_mgr = ProviderManager(pool)
    await provider_mgr.init()

    # 初始化记忆存储
    memory_store = MemoryStore(pool, provider_mgr.get_embedding_provider())

    # 初始化工具注册表与插件子系统（插件可注册工具、调用内置能力、直连协议端）
    registry = tool_runtime.get_registry()
    plugin_manager = PluginManager(
        registry=registry,
        plugin_dir=settings.plugins_dir,
        state_store=DbPluginStateStore(pool),
        adapter_router=router,
        message_service=message_service,
        store=store,
        pool=pool,
        provider_mgr=provider_mgr,
        memory_store=memory_store,
    )
    await plugin_manager.init()

    # OneBot 连接管理：DB 持久化，支持多连接、手动停止与自动重连
    async def _on_onebot_event(
        adapter: PlatformAdapter,
        event: dict[str, Any],
        session: aiohttp.ClientSession,
    ) -> None:
        await handle_event(
            adapter,
            event,
            message_service,
            store,
            provider_mgr,
            session,
            memory_store=memory_store,
        )

    connection_manager = OneBotConnectionManager(
        pool=pool,
        platform_store=platform_store,
        router=router,
        message_service=message_service,
        store=store,
        provider_mgr=provider_mgr,
        memory_store=memory_store,
        on_event=_on_onebot_event,
    )
    await connection_manager.init()

    # 启动 HTTP API server（非阻塞）
    app = await create_app(
        pool=pool,
        provider_mgr=provider_mgr,
        memory_store=memory_store,
        tool_registry=registry,
        adapter_router=router,
        plugin_manager=plugin_manager,
        connection_manager=connection_manager,
    )
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.api_host, settings.api_port)
    await site.start()
    logger.info("API server listening on %s:%d", settings.api_host, settings.api_port)

    # 启动后台数据清理任务
    cleanup_task = asyncio.create_task(run_cleanup_loop(pool))

    try:
        await asyncio.Event().wait()
    finally:
        cleanup_task.cancel()
        await connection_manager.close()
        await plugin_manager.close()
        await runner.cleanup()
        await provider_mgr.close()
        await close_db()


def main() -> None:
    """CLI entry point."""
    # ── 日志配置 ──────────────────────────────────────────
    # 自定义 TRACE 级别（比 DEBUG 更低，记录完整 prompt/response）
    trace_level = 5
    logging.addLevelName(trace_level, "TRACE")

    # 控制台：INFO 级别，人类可读
    # 文件：  TRACE 级别，包含完整 LLM 请求/响应（等 runtime_config 加载后再建）
    root_logger = logging.getLogger()
    root_logger.setLevel(trace_level)
    root_logger.addHandler(_console_handler())

    # 压制 aiohttp access log（每个 HTTP 请求都输出 INFO，WebUI 连上就刷屏）
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logger.info("Shutting down.")


def _log_timezone() -> ZoneInfo:
    return ZoneInfo(str(runtime_config.get("timezone") or settings.timezone))


def _console_handler() -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_TzFormatter(_LOG_FMT, _log_timezone()))
    return handler


def _configure_file_logging() -> None:
    """按 runtime_config 里的值建立/重建文件 handler（启动时调用一次）。"""
    root_logger = logging.getLogger()
    for handler in [h for h in root_logger.handlers if isinstance(h, RotatingFileHandler)]:
        root_logger.removeHandler(handler)
        handler.close()
    for handler in root_logger.handlers:
        handler.setFormatter(_TzFormatter(_LOG_FMT, _log_timezone()))
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "sophos.log",
        maxBytes=int(runtime_config.get("log_max_bytes") or settings.log_max_bytes),
        backupCount=int(runtime_config.get("log_backup_count") or settings.log_backup_count),
        encoding="utf-8",
    )
    file_handler.setLevel(5)
    file_handler.setFormatter(_TzFormatter(_LOG_FMT, _log_timezone()))
    root_logger.addHandler(file_handler)


if __name__ == "__main__":
    main()
