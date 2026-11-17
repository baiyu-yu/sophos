import math
import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sophos.api.routes import permissions as permissions_routes
from sophos.api.routes.permissions import (
    _parse_float,
    _parse_int,
    _validate_scope,
    routes,
)


class PermissionApiValidationTests(unittest.TestCase):
    def test_valid_scopes(self) -> None:
        _validate_scope("global", 0)
        _validate_scope("conversation", 123)

    def test_invalid_scope_combinations_are_rejected(self) -> None:
        for scope_type, scope_id in (
            ("global", 1),
            ("conversation", 0),
            ("group", 1),
            ("private", 1),
            ("other", 1),
        ):
            with self.subTest(scope_type=scope_type, scope_id=scope_id), self.assertRaises(web.HTTPBadRequest):
                _validate_scope(scope_type, scope_id)

    def test_numeric_parsers_reject_invalid_values(self) -> None:
        self.assertEqual(_parse_int("123", "id"), 123)
        self.assertEqual(_parse_float("1.5", "rate"), 1.5)
        with self.assertRaises(web.HTTPBadRequest):
            _parse_int("abc", "id")
        with self.assertRaises(web.HTTPBadRequest):
            _parse_float("abc", "rate")
        self.assertTrue(math.isnan(_parse_float("nan", "rate")))

    def test_expected_routes_are_registered(self) -> None:
        registered = {(route.method, route.path) for route in routes}
        self.assertIn(("GET", "/api/permissions/users"), registered)
        self.assertIn(("GET", "/api/permissions/conversations"), registered)
        self.assertIn(("GET", "/api/permissions/scopes"), registered)
        self.assertIn(("PUT", "/api/permissions/scopes/{scope_type}/{scope_id}/tools"), registered)
        self.assertIn(("POST", "/api/permissions/grants"), registered)
        self.assertIn(("POST", "/api/permissions/policies"), registered)
        self.assertIn(("GET", "/api/permissions/masters"), registered)
        self.assertIn(("POST", "/api/permissions/masters"), registered)
        self.assertIn(("DELETE", "/api/permissions/masters/{user_id}"), registered)


class MasterRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        app = web.Application()
        app["pool"] = object()
        app.router.add_routes(routes)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_grant_master(self) -> None:
        with (
            patch.object(permissions_routes.permission, "grant_master", AsyncMock(return_value=True)),
            patch.object(permissions_routes, "_require_user", AsyncMock()),
        ):
            response = await self.client.post("/api/permissions/masters", json={"user_id": 5})
            self.assertEqual(response.status, 200)
            self.assertIn("设为 Master", (await response.json())["message"])

    async def test_cannot_revoke_last_master(self) -> None:
        with patch.object(
            permissions_routes.permission,
            "list_masters",
            AsyncMock(return_value=[{"user_id": 1, "display_name": "master"}]),
        ):
            response = await self.client.delete("/api/permissions/masters/1")
            self.assertEqual(response.status, 400)

    async def test_revoke_missing_master_returns_404(self) -> None:
        with (
            patch.object(
                permissions_routes.permission,
                "list_masters",
                AsyncMock(return_value=[{"user_id": 1, "display_name": "a"}, {"user_id": 2, "display_name": "b"}]),
            ),
            patch.object(permissions_routes.permission, "revoke_master", AsyncMock(return_value=False)),
        ):
            response = await self.client.delete("/api/permissions/masters/9")
            self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()
