"""插件状态存储 — 启用开关与配置持久化。

默认实现使用 PostgreSQL 的 ``plugins`` 表；测试或嵌入式场景可以使用
``MemoryPluginStateStore``。插件文件本身不保存状态，删除/新增插件目录不会
丢失管理端设置的开关和配置。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PluginState:
    """某个插件的持久化状态。"""

    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)


class PluginStateStore(Protocol):
    """状态存储接口；实现方需要保证读写幂等。"""

    async def load_all(self) -> dict[str, PluginState]: ...

    async def set_enabled(self, name: str, enabled: bool) -> None: ...

    async def set_config(self, name: str, config: dict[str, Any]) -> None: ...


def decode_jsonb(value: Any) -> dict[str, Any]:
    """asyncpg 未注册 JSONB codec，读出来是字符串；这里统一成 dict。"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("插件配置不是合法 JSON，已忽略: %r", value)
            return {}
    return dict(value) if isinstance(value, dict) else {}


class DbPluginStateStore:
    """基于 ``plugins`` 表的状态存储。"""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def load_all(self) -> dict[str, PluginState]:
        rows = await self._pool.fetch("SELECT name, enabled, config FROM plugins")
        return {
            row["name"]: PluginState(
                enabled=bool(row["enabled"]),
                config=decode_jsonb(row["config"]),
            )
            for row in rows
        }

    async def set_enabled(self, name: str, enabled: bool) -> None:
        await self._pool.execute(
            """
            INSERT INTO plugins (name, enabled)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE
            SET enabled = EXCLUDED.enabled, updated_at = now()
            """,
            name,
            enabled,
        )

    async def set_config(self, name: str, config: dict[str, Any]) -> None:
        await self._pool.execute(
            """
            INSERT INTO plugins (name, config)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (name) DO UPDATE
            SET config = EXCLUDED.config, updated_at = now()
            """,
            name,
            json.dumps(config, ensure_ascii=False),
        )


class MemoryPluginStateStore:
    """内存状态存储，主要用于测试与无数据库的嵌入式运行。"""

    def __init__(self) -> None:
        self._states: dict[str, PluginState] = {}

    async def load_all(self) -> dict[str, PluginState]:
        return {
            name: PluginState(enabled=state.enabled, config=dict(state.config))
            for name, state in self._states.items()
        }

    async def set_enabled(self, name: str, enabled: bool) -> None:
        state = self._states.setdefault(name, PluginState())
        state.enabled = enabled

    async def set_config(self, name: str, config: dict[str, Any]) -> None:
        state = self._states.setdefault(name, PluginState())
        state.config = dict(config)

    def seed(self, name: str, *, enabled: bool = True, config: dict[str, Any] | None = None) -> None:
        """测试辅助：预置某个插件的状态。"""
        self._states[name] = PluginState(enabled=enabled, config=dict(config or {}))
