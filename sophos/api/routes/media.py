"""媒体文件访问：把本地保存的图片暴露为长期可用的静态资源。"""

from __future__ import annotations

from aiohttp import web

from sophos import media

routes = web.RouteTableDef()


@routes.get("/media/{filename}")
async def get_media(request: web.Request) -> web.StreamResponse:
    """返回媒体目录里的图片文件。文件名必须是 ``<图片编码>.<扩展名>``。"""
    filename = request.match_info["filename"]
    if not media.FILENAME_RE.match(filename):
        raise web.HTTPNotFound(reason="media not found")
    path = media.media_root() / filename
    if not path.is_file():
        raise web.HTTPNotFound(reason="media not found")
    return web.FileResponse(
        path,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
