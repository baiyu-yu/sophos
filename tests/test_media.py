"""图片落盘、图片编码解析与图片工具测试。"""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sophos import image_host, media, runtime_config
from sophos.platform import SentMessage
from sophos.tools.media import SaveImageTool, SendImageTool
from sophos.tools.web import ViewImageTool

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class MediaStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        patcher = patch.dict(
            runtime_config._cache,
            {"media_dir": str(self.root), "media_public_base_url": "https://cdn.example.com/media"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_and_find_image(self) -> None:
        code = media.save_image_bytes(_PNG_BYTES, "image/png", code="abcdef0123456789")
        self.assertEqual(code, "abcdef0123456789")
        path = media.find_image("abcdef0123456789")
        self.assertIsNotNone(path)
        self.assertEqual(path.name, "abcdef0123456789.png")
        self.assertEqual(path.read_bytes(), _PNG_BYTES)
        self.assertEqual(media.public_url(code), "https://cdn.example.com/media/abcdef0123456789.png")

    def test_normalize_code_accepts_context_snippet(self) -> None:
        self.assertEqual(media.normalize_code("[图片(abcdef0123456789): 一只猫]"), "abcdef0123456789")
        self.assertEqual(media.normalize_code("ABCDEF0123456789"), "abcdef0123456789")
        self.assertIsNone(media.normalize_code("not-a-code"))

    def test_unsupported_mime_is_not_saved(self) -> None:
        self.assertIsNone(media.save_image_bytes(b"data", "application/pdf"))

    def test_filename_whitelist_blocks_traversal(self) -> None:
        self.assertTrue(media.FILENAME_RE.match("abcdef0123456789.png"))
        self.assertFalse(media.FILENAME_RE.match("../etc/passwd"))
        self.assertFalse(media.FILENAME_RE.match("abcdef0123456789.svg"))

    def test_missing_code_returns_none(self) -> None:
        self.assertIsNone(media.find_image("deadbeefdeadbeef"))
        self.assertIsNone(media.read_image("deadbeefdeadbeef"))


class SendImageToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_stored_image_as_inline_base64(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(runtime_config._cache, {"media_dir": tmp}):
            code = media.save_image_bytes(_PNG_BYTES, "image/png", code="abcdef0123456789")
            service = AsyncMock()
            service.send_message.return_value = SentMessage(
                message_id=12, conversation_id=3, external_message_id="99"
            )
            result = await SendImageTool().execute(
                {"image_code": code, "text": "看图"},
                {"conversation_id": 3, "message_service": service},
            )
            self.assertEqual(result["status"], "ok")
            request = service.send_message.await_args.args[0]
            self.assertEqual(request.conversation_id, 3)
            self.assertEqual(request.text, "看图")
            self.assertEqual(len(request.inline_media), 1)
            payload = request.inline_media[0]
            self.assertEqual(payload["type"], "image")
            self.assertEqual(base64.b64decode(payload["data"]["base64"]), _PNG_BYTES)

    async def test_missing_image_returns_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(runtime_config._cache, {"media_dir": tmp}):
            result = await SendImageTool().execute(
                {"image_code": "deadbeefdeadbeef"},
                {"conversation_id": 3, "message_service": AsyncMock()},
            )
        self.assertIn("error", result)


class SaveImageToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_only_returns_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            runtime_config._cache, {"media_dir": tmp, "media_public_base_url": ""}
        ):
            code = media.save_image_bytes(_PNG_BYTES, "image/png", code="abcdef0123456789")
            result = await SaveImageTool().execute({"image_code": code}, {})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["image_code"], code)
        self.assertTrue(result["path"].endswith("abcdef0123456789.png"))
        self.assertEqual(result["url"], "")

    async def test_upload_requires_configured_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            runtime_config._cache,
            {"media_dir": tmp, "image_host_url": "", "media_public_base_url": ""},
        ):
            code = media.save_image_bytes(_PNG_BYTES, "image/png", code="abcdef0123456789")
            result = await SaveImageTool().execute({"image_code": code, "upload": True}, {})
        self.assertIn("图床", result["error"])

    async def test_upload_returns_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            runtime_config._cache,
            {
                "media_dir": tmp,
                "image_host_url": "https://img.example.com/upload",
                "media_public_base_url": "",
            },
        ):
            code = media.save_image_bytes(_PNG_BYTES, "image/png", code="abcdef0123456789")
            with patch.object(
                image_host,
                "upload_image",
                new=AsyncMock(return_value="https://img.example.com/i/abcdef.png"),
            ):
                result = await SaveImageTool().execute({"image_code": code, "upload": True}, {})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["url"], "https://img.example.com/i/abcdef.png")


class ViewImageToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tool = ViewImageTool()

    def test_description_tells_model_not_to_build_urls(self) -> None:
        text = self.tool.description
        self.assertIn("image_code", text)
        self.assertIn("不要自己构造", text)

    async def test_unreachable_url_returns_image_code_hint(self) -> None:
        result = await self.tool.execute(
            {"url": "http://127.0.0.1:9/pic.png"}, {"vision_provider": object()}
        )
        self.assertIn("抓取失败", result["error"])
        self.assertIn("image_code", result["hint"])

    async def test_unknown_code_returns_hint(self) -> None:
        result = await self.tool.execute(
            {"image_code": "ffffffffffffffff"}, {"vision_provider": object()}
        )
        self.assertIn("尚未保存", result["error"])
        self.assertIn("不要自己构造编码", result["hint"])


class ImageHostPayloadTests(unittest.TestCase):
    def test_extracts_url_from_common_shapes(self) -> None:
        self.assertEqual(image_host._url_from_payload({"url": "https://a/1.png"}), "https://a/1.png")
        self.assertEqual(
            image_host._url_from_payload({"data": {"links": {"url": "https://a/2.png"}}}),
            "https://a/2.png",
        )
        self.assertEqual(
            image_host._url_from_payload({"data": [{"url": "https://a/3.png"}]}),
            "https://a/3.png",
        )
        self.assertIsNone(image_host._url_from_payload({"ok": True}))


if __name__ == "__main__":
    unittest.main()
