"""OneBot 连接管理 API 与参数校验测试。"""

from __future__ import annotations

import unittest
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sophos.api.routes.connections import routes
from sophos.connections import (
    ConnectionNotFoundError,
    ConnectionValidationError,
    OneBotConnectionManager,
)


class _FakeManager:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = [
            {
                "id": 1,
                "name": "默认连接",
                "ws_url": "ws://localhost:3001",
                "enabled": True,
                "auto_reconnect": True,
                "reconnect_interval": 5,
                "has_token": False,
                "state": "stopped",
                "error": "",
                "attempts": 0,
                "connected_at": "",
                "self_id": "",
                "nickname": "",
            }
        ]

    def _get(self, connection_id: int) -> dict[str, Any]:
        for item in self.items:
            if item["id"] == connection_id:
                return item
        raise ConnectionNotFoundError(f"连接 {connection_id} 不存在")

    def list_connections(self) -> list[dict[str, Any]]:
        return list(self.items)

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
        if not name:
            raise ConnectionValidationError("连接名称不能为空")
        item = {
            "id": len(self.items) + 1,
            "name": name,
            "ws_url": ws_url,
            "enabled": enabled,
            "auto_reconnect": auto_reconnect,
            "reconnect_interval": reconnect_interval,
            "has_token": bool(token),
            "state": "connecting" if enabled else "stopped",
            "error": "",
            "attempts": 0,
            "connected_at": "",
            "self_id": "",
            "nickname": "",
        }
        self.items.append(item)
        return item

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
        item = self._get(connection_id)
        if name is not None:
            item["name"] = name
        if ws_url is not None:
            item["ws_url"] = ws_url
        if token is not None:
            item["has_token"] = bool(token)
        if enabled is not None:
            item["enabled"] = enabled
        if auto_reconnect is not None:
            item["auto_reconnect"] = auto_reconnect
        if reconnect_interval is not None:
            item["reconnect_interval"] = reconnect_interval
        return item

    async def delete_connection(self, connection_id: int) -> None:
        self._get(connection_id)
        self.items = [item for item in self.items if item["id"] != connection_id]

    async def start_connection(self, connection_id: int) -> dict[str, Any]:
        item = self._get(connection_id)
        item["state"] = "connecting"
        item["enabled"] = True
        return item

    async def stop_connection(self, connection_id: int) -> dict[str, Any]:
        item = self._get(connection_id)
        item["state"] = "stopped"
        return item

    async def restart_connection(self, connection_id: int) -> dict[str, Any]:
        item = self._get(connection_id)
        item["state"] = "connecting"
        return item


class ConnectionRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.manager = _FakeManager()
        app = web.Application()
        app["connection_manager"] = self.manager
        app.router.add_routes(routes)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_list_connections(self) -> None:
        response = await self.client.get("/api/connections")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(len(payload["connections"]), 1)
        self.assertEqual(payload["connections"][0]["name"], "默认连接")

    async def test_create_connection(self) -> None:
        response = await self.client.post(
            "/api/connections",
            json={
                "name": "备用机器人",
                "ws_url": "ws://127.0.0.1:3002",
                "token": "secret",
                "enabled": False,
                "reconnect_interval": 10,
            },
        )
        self.assertEqual(response.status, 201)
        payload = await response.json()
        self.assertIn("已创建", payload["message"])
        self.assertEqual(payload["connection"]["name"], "备用机器人")
        self.assertTrue(payload["connection"]["has_token"])
        self.assertFalse(payload["connection"]["enabled"])

    async def test_create_requires_name(self) -> None:
        response = await self.client.post(
            "/api/connections",
            json={"name": "", "ws_url": "ws://127.0.0.1:3002"},
        )
        self.assertEqual(response.status, 400)

    async def test_update_connection(self) -> None:
        response = await self.client.put(
            "/api/connections/1",
            json={"name": "主机器人", "auto_reconnect": False},
        )
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload["connection"]["name"], "主机器人")
        self.assertFalse(payload["connection"]["auto_reconnect"])

    async def test_update_missing_connection(self) -> None:
        response = await self.client.put("/api/connections/99", json={"name": "x"})
        self.assertEqual(response.status, 404)

    async def test_delete_connection(self) -> None:
        response = await self.client.delete("/api/connections/1")
        self.assertEqual(response.status, 200)
        payload = await response.json()
        self.assertEqual(payload["connections"], [])
        self.assertEqual(self.manager.items, [])

    async def test_start_stop_restart(self) -> None:
        stopped = await self.client.post("/api/connections/1/stop")
        self.assertEqual(stopped.status, 200)
        self.assertEqual((await stopped.json())["connection"]["state"], "stopped")

        started = await self.client.post("/api/connections/1/start")
        self.assertEqual(started.status, 200)
        self.assertEqual((await started.json())["connection"]["state"], "connecting")

        restarted = await self.client.post("/api/connections/1/restart")
        self.assertEqual(restarted.status, 200)

    async def test_invalid_json(self) -> None:
        response = await self.client.post(
            "/api/connections",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status, 400)

    async def test_missing_manager_returns_503(self) -> None:
        app = web.Application()
        app.router.add_routes(routes)
        async with TestClient(TestServer(app)) as client:
            response = await client.get("/api/connections")
            self.assertEqual(response.status, 503)


class ConnectionValidationTests(unittest.TestCase):
    def test_reconnect_interval_bounds(self) -> None:
        self.assertEqual(OneBotConnectionManager._validate_interval(5), 5)
        for value in (0, 601):
            with self.assertRaises(ConnectionValidationError):
                OneBotConnectionManager._validate_interval(value)

    def test_ws_url_scheme(self) -> None:
        OneBotConnectionManager._validate_url("ws://127.0.0.1:3001")
        OneBotConnectionManager._validate_url("wss://example.com/onebot")
        for value in ("", "http://127.0.0.1:3001"):
            with self.assertRaises(ConnectionValidationError):
                OneBotConnectionManager._validate_url(value)


if __name__ == "__main__":
    unittest.main()
