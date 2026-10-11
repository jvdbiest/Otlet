# SPDX-License-Identifier: AGPL-3.0-or-later
"""ASGI application: health endpoint and the built interface served as static files (TC-03)."""

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from otlet import __version__
from otlet.platform.config import Settings


class SinglePageApp(StaticFiles):
    """Static files that fall back to index.html for client-side routes (paths whose last
    segment has no file extension), so reloading /library/42 serves the interface."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="Otlet",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    if settings.ui_dir is not None and settings.ui_dir.is_dir():
        app.mount("/", SinglePageApp(directory=settings.ui_dir, html=True), name="ui")
    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_env())
