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
    # 文件：  TRACE 级别，包含完整 LLM 请求/响应
    log_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    class _TzFormatter(logging.Formatter):
        """用配置时区替代本地时间的 Formatter。"""

        _tz = ZoneInfo(settings.timezone)

        @override
        def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
            dt = datetime.fromtimestamp(record.created, tz=self._tz)
            if datefmt:
                return dt.strftime(datefmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"

    root_logger = logging.getLogger()
    root_logger.setLevel(trace_level)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_TzFormatter(log_fmt))
    root_logger.addHandler(console_handler)

    # 文件 handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "sophos.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(trace_level)
    file_handler.setFormatter(_TzFormatter(log_fmt))
    root_logger.addHandler(file_handler)

    # 压制 aiohttp access log（每个 HTTP 请求都输出 INFO，WebUI 连上就刷屏）
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
