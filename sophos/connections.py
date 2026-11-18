"""OneBot WebSocket 连接管理：DB 持久化、热重载、手动断开与自动重连。"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp
import asyncpg

from sophos import runtime_config
from sophos.adapter_router import AdapterRouter
from sophos.config import settings
from sophos.onebot_adapter import OneBot11Adapter
from sophos.onebot_api import OneBotAPI, OneBotAPIError
from sophos.platform import MessagingAdapter
from sophos.platform_store import PlatformStore

logger = logging.getLogger(__name__)

STATE_STOPPED = "stopped"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_ERROR = "error"

MIN_RECONNECT_INTERVAL = 1
MAX_RECONNECT_INTERVAL = 600

EventCallback = Callable[[MessagingAdapter, dict[str, Any], aiohttp.ClientSession], Awaitable[None]]


class ConnectionManagerError(RuntimeError):
    """连接管理相关的业务错误。"""


class ConnectionNotFoundError(ConnectionManagerError):
    """连接 ID 不存在。"""


class ConnectionValidationError(ConnectionManagerError):
    """连接参数非法。"""


@dataclass(slots=True)
class ConnectionRecord:
    id: int
    name: str
    ws_url: str
    token: str = ""
    enabled: bool = True
    auto_reconnect: bool = True
    reconnect_interval: int = 5

    @classmethod
    def from_row(cls, row: asyncpg.Record) -> ConnectionRecord:
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            ws_url=str(row["ws_url"]),
            token=str(row["token"] or ""),
            enabled=bool(row["enabled"]),
            auto_reconnect=bool(row["auto_reconnect"]),
            reconnect_interval=int(row["reconnect_interval"]),
        )

    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


@dataclass(slots=True)
class ConnectionStatus:
    state: str = STATE_STOPPED
    error: str = ""
    attempts: int = 0
    connected_at: str = ""
    self_id: str = ""
    nickname: str = ""


class OneBotConnectionManager:
    """维护多个 OneBot 连接；每个连接独立重连，可单独停止。"""

    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        platform_store: PlatformStore,
        router: AdapterRouter,
        message_service: Any,
        store: Any,
        provider_mgr: Any,
        memory_store: Any | None = None,
        on_event: EventCallback | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._pool = pool
        self._platform_store = platform_store
        self._router = router
        self._message_service = message_service
        self._store = store
        self._provider_mgr = provider_mgr
        self._memory_store = memory_store
        self._on_event = on_event
        self._session = session
        self._owns_session = session is None
        self._records: dict[int, ConnectionRecord] = {}
        self._status: dict[int, ConnectionStatus] = {}
        self._adapters: dict[int, MessagingAdapter] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    # ── 生命周期 ────────────────────────────────────────

    async def init(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        await self._seed_default()
        await self._load()
        for record in list(self._records.values()):
            if record.enabled:
                self._start(record)

    async def close(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    # ── 查询 ────────────────────────────────────────────

    def list_connections(self) -> list[dict[str, Any]]:
        items = [self.describe(record) for record in self._records.values()]
        items.sort(key=lambda item: item["id"])
        return items

    def describe(self, record: ConnectionRecord) -> dict[str, Any]:
        status = self._status.setdefault(record.id, ConnectionStatus())
        return {
            "id": record.id,
            "name": record.name,
            "ws_url": record.ws_url,
            "enabled": record.enabled,
            "auto_reconnect": record.auto_reconnect,
            "reconnect_interval": record.reconnect_interval,
            "has_token": bool(record.token),
            "state": status.state,
            "error": status.error,
            "attempts": status.attempts,
            "connected_at": status.connected_at,
            "self_id": status.self_id,
            "nickname": status.nickname,
        }

    def _require(self, connection_id: int) -> ConnectionRecord:
        record = self._records.get(connection_id)
        if record is None:
            raise ConnectionNotFoundError(f"连接 {connection_id} 不存在")
        return record

    # ── 增删改 ──────────────────────────────────────────

    async def create_connection(
        self,
        *,
        name: str,
        ws_url: str,
        token: str = "",
        enabled: bool = True,
        auto_reconnect: bool = True,
        reconnect_interval: int = 5,
    ) -> dict[str, Any]:
        name = (name or "").strip()
        ws_url = (ws_url or "").strip()
        if not name:
            raise ConnectionValidationError("连接名称不能为空")
        if len(name) > 64:
            raise ConnectionValidationError("连接名称不能超过 64 个字符")
        self._validate_url(ws_url)
        interval = self._validate_interval(reconnect_interval)
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO onebot_connections (name, ws_url, token, enabled, auto_reconnect, reconnect_interval)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                name,
                ws_url,
                token or "",
                enabled,
                auto_reconnect,
                interval,
            )
        except asyncpg.UniqueViolationError as exc:
            raise ConnectionValidationError(f"连接名称 '{name}' 已存在") from exc
        assert row is not None
        record = ConnectionRecord.from_row(row)

        self._records[record.id] = record
        self._status[record.id] = ConnectionStatus()
        if record.enabled:
            self._start(record)
        return self.describe(record)

    async def update_connection(
        self,
        connection_id: int,
        *,
        name: str | None = None,
        ws_url: str | None = None,
        token: str | None = None,
        enabled: bool | None = None,
        auto_reconnect: bool | None = None,
        reconnect_interval: int | None = None,
    ) -> dict[str, Any]:
        record = self._require(connection_id)
        new_name = record.name if name is None else name.strip()
        new_url = record.ws_url if ws_url is None else ws_url.strip()
        new_token = record.token if token is None else token
        new_enabled = record.enabled if enabled is None else bool(enabled)
        new_auto = record.auto_reconnect if auto_reconnect is None else bool(auto_reconnect)
        new_interval = (
            record.reconnect_interval
            if reconnect_interval is None
            else self._validate_interval(reconnect_interval)
        )
        if not new_name:
            raise ConnectionValidationError("连接名称不能为空")
        self._validate_url(new_url)
        try:
            row = await self._pool.fetchrow(
                """
                UPDATE onebot_connections
                SET name = $2, ws_url = $3, token = $4, enabled = $5,
                    auto_reconnect = $6, reconnect_interval = $7, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                connection_id,
                new_name,
                new_url,
                new_token,
                new_enabled,
                new_auto,
                new_interval,
            )
        except asyncpg.UniqueViolationError as exc:
            raise ConnectionValidationError(f"连接名称 '{new_name}' 已存在") from exc
        if row is None:
            raise ConnectionNotFoundError(f"连接 {connection_id} 不存在")
        self._records[connection_id] = ConnectionRecord.from_row(row)
        await self._apply(connection_id)
        return self.describe(self._records[connection_id])

    async def delete_connection(self, connection_id: int) -> None:
        self._require(connection_id)
        await self._stop(connection_id)
        await self._pool.execute("DELETE FROM onebot_connections WHERE id = $1", connection_id)
        self._records.pop(connection_id, None)
        self._status.pop(connection_id, None)
        self._adapters.pop(connection_id, None)
        self._tasks.pop(connection_id, None)

    async def start_connection(self, connection_id: int) -> dict[str, Any]:
        record = self._require(connection_id)
        if not record.enabled:
            record = self._records[connection_id] = await self._set_enabled(connection_id, True)
        self._start(record)
        return self.describe(record)

    async def stop_connection(self, connection_id: int) -> dict[str, Any]:
        record = self._require(connection_id)
        await self._stop(connection_id)
        if record.enabled:
            record = self._records[connection_id] = await self._set_enabled(connection_id, False)
        status = self._status.setdefault(connection_id, ConnectionStatus())
        status.state = STATE_STOPPED
        return self.describe(record)

    async def restart_connection(self, connection_id: int) -> dict[str, Any]:
        record = self._require(connection_id)
        await self._stop(connection_id)
        if not record.enabled:
            self._records[connection_id] = record = await self._set_enabled(connection_id, True)
        self._start(record)
        return self.describe(record)

    # ── 内部 ────────────────────────────────────────────

    @staticmethod
    def _validate_url(ws_url: str) -> None:
        if not ws_url:
            raise ConnectionValidationError("WebSocket 地址不能为空")
        if not ws_url.startswith(("ws://", "wss://")):
            raise ConnectionValidationError("WebSocket 地址必须以 ws:// 或 wss:// 开头")

    @staticmethod
    def _validate_interval(value: int) -> int:
        try:
            interval = int(value)
        except (TypeError, ValueError) as exc:
            raise ConnectionValidationError("重连间隔必须是整数秒") from exc
        if not MIN_RECONNECT_INTERVAL <= interval <= MAX_RECONNECT_INTERVAL:
            raise ConnectionValidationError(
                f"重连间隔必须在 {MIN_RECONNECT_INTERVAL}~{MAX_RECONNECT_INTERVAL} 秒之间"
            )
        return interval

    async def _set_enabled(self, connection_id: int, enabled: bool) -> ConnectionRecord:
        row = await self._pool.fetchrow(
            "UPDATE onebot_connections SET enabled = $2, updated_at = now() WHERE id = $1 RETURNING *",
            connection_id,
            enabled,
        )
        if row is None:
            raise ConnectionNotFoundError(f"连接 {connection_id} 不存在")
        return ConnectionRecord.from_row(row)

    async def _seed_default(self) -> None:
        count = await self._pool.fetchval("SELECT count(*) FROM onebot_connections")
        if count:
            return
        ws_url = settings.onebot_ws_url
        if not ws_url:
            return
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO onebot_connections (name, ws_url, token, enabled, auto_reconnect)
                VALUES ($1, $2, $3, TRUE, TRUE)
                RETURNING *
                """,
                "默认连接",
                ws_url,
                settings.onebot_ws_token or "",
            )
            logger.info("Seeded OneBot connection from ONEBOT_WS_URL (%s)", ws_url)
            if row is not None:
                self._records[int(row["id"])] = ConnectionRecord.from_row(row)
        except asyncpg.UniqueViolationError:
            logger.info("OneBot connection already seeded")

    async def _load(self) -> None:
        rows = await self._pool.fetch("SELECT * FROM onebot_connections ORDER BY id")
        for row in rows:
            record = ConnectionRecord.from_row(row)
            self._records[record.id] = record
            self._status.setdefault(record.id, ConnectionStatus())

    async def _apply(self, connection_id: int) -> None:
        record = self._records[connection_id]
        await self._stop(connection_id)
        if record.enabled:
            self._start(record)

    def _start(self, record: ConnectionRecord) -> None:
        if not record.enabled:
            return
        if self._session is None:
            return
        task = self._tasks.get(record.id)
        if task is not None and not task.done():
            return
        status = self._status.setdefault(record.id, ConnectionStatus())
        status.state = STATE_CONNECTING
        status.error = ""
        self._tasks[record.id] = asyncio.create_task(
            self._run(record.id),
            name=f"onebot-connection-{record.id}",
        )

    async def _stop(self, connection_id: int) -> None:
        task = self._tasks.pop(connection_id, None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._unregister(connection_id)
        status = self._status.setdefault(connection_id, ConnectionStatus())
        status.state = STATE_STOPPED

    def _unregister(self, connection_id: int) -> None:
        adapter = self._adapters.pop(connection_id, None)
        if adapter is not None:
            self._router.unregister(adapter)

    async def _run(self, connection_id: int) -> None:
        status = self._status.setdefault(connection_id, ConnectionStatus())
        while True:
            record = self._records.get(connection_id)
            if record is None or not record.enabled:
                status.state = STATE_STOPPED
                return
            status.state = STATE_CONNECTING
            status.error = ""
            status.attempts += 1
            try:
                await self._run_once(record, status)
            except asyncio.CancelledError:
                status.state = STATE_STOPPED
                raise
            except (aiohttp.ClientError, OSError, TimeoutError, OneBotAPIError) as exc:
                status.state = STATE_ERROR
                status.error = f"{type(exc).__name__}: {exc}"
                logger.warning("OneBot 连接 %s 失败：%s", record.name, exc)
            except Exception as exc:  # noqa: BLE001 - 单连接错误不应结束进程
                status.state = STATE_ERROR
                status.error = f"{type(exc).__name__}: {exc}"
                logger.exception("OneBot 连接 %s 出现未预期错误", record.name)
            finally:
                self._unregister(connection_id)
            record = self._records.get(connection_id)
            if record is None or not record.enabled:
                status.state = STATE_STOPPED
                return
            if not record.auto_reconnect:
                status.state = STATE_STOPPED
                status.error = status.error or "连接已断开（未开启自动重连）"
                return
            await asyncio.sleep(max(MIN_RECONNECT_INTERVAL, record.reconnect_interval))

    async def _run_once(self, record: ConnectionRecord, status: ConnectionStatus) -> None:
        assert self._session is not None
        logger.info("正在连接 OneBot：%s（%s）", record.name, record.ws_url)
        async with self._session.ws_connect(
            record.ws_url,
            headers=record.headers(),
            heartbeat=30,
        ) as ws:
            api = OneBotAPI(ws)
            holder: dict[str, Any] = {"adapter": None}
            pump = asyncio.create_task(self._read_loop(record, ws, api, holder))
            try:
                adapter = await self._ensure_adapter(record, api, holder)
                self._router.register(adapter)
                status.state = STATE_CONNECTED
                status.attempts = 0
                status.connected_at = datetime.now(UTC).isoformat()
                await pump
            finally:
                pump.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await pump
                self._unregister(record.id)
                api.cancel_all("connection closed")
                status.connected_at = ""

    async def _ensure_adapter(
        self,
        record: ConnectionRecord,
        api: OneBotAPI,
        holder: dict[str, Any],
    ) -> MessagingAdapter:
        existing = holder.get("adapter")
        if existing is not None:
            return existing
        self_id = ""
        nickname = ""
        with contextlib.suppress(TimeoutError, OneBotAPIError, aiohttp.ClientError):
            info = await api.call("get_login_info")
            self_id = str(info.get("user_id") or "")
            nickname = str(info.get("nickname") or "")
        if not self_id:
            self_id = str(runtime_config.get("bot_id") or f"connection-{record.id}")
            nickname = str(runtime_config.get("bot_nickname") or "")
        adapter = await OneBot11Adapter.create(
            api=api,
            platform_store=self._platform_store,
            self_external_id=self_id,
            display_name=nickname,
            binding_name=f"connection-{record.id}",
        )
        holder["adapter"] = adapter
        status = self._status.setdefault(record.id, ConnectionStatus())
        status.self_id = self_id
        status.nickname = nickname
        return adapter

    async def _read_loop(
        self,
        record: ConnectionRecord,
        ws: aiohttp.ClientWebSocketResponse,
        api: OneBotAPI,
        holder: dict[str, Any],
    ) -> None:
        async for message in ws:
            if message.type == aiohttp.WSMsgType.TEXT:
                try:
                    data: dict[str, Any] = json.loads(message.data)
                except json.JSONDecodeError:
                    continue
                event = api.dispatch(data)
                if event is None:
                    continue
                adapter = holder.get("adapter")
                if adapter is None:
                    try:
                        adapter = await self._ensure_adapter(record, api, holder)
                        self._router.register(adapter)
                    except Exception as exc:  # noqa: BLE001 - 事件不应打断连接
                        logger.warning("OneBot 连接 %s 建立适配器失败：%s", record.name, exc)
                        continue
                if self._on_event is not None:
                    asyncio.create_task(self._dispatch(adapter, event))
            elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    async def _dispatch(self, adapter: MessagingAdapter, event: dict[str, Any]) -> None:
        assert self._session is not None
        assert self._on_event is not None
        try:
            await self._on_event(adapter, event, self._session)
        except Exception:  # noqa: BLE001 - 单条事件失败不影响连接
            logger.exception("处理 OneBot 事件失败")
