"""Healthcheck endpoint для мониторинга."""
from __future__ import annotations

import time
from aiohttp import web

_START_TIME = time.time()


async def health_handler(request: web.Request) -> web.Response:
    uptime = int(time.time() - _START_TIME)
    return web.json_response({"status": "ok", "uptime": uptime})


def create_health_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    return app
