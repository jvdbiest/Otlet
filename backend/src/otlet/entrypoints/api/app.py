# SPDX-License-Identifier: AGPL-3.0-or-later
"""ASGI application: health endpoint and the built interface served as static files (TC-03)."""

import logging
from collections.abc import Sequence
from pathlib import PurePath
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from otlet import __version__
from otlet.ai.adapters.budget_postgres import PostgresBudget
from otlet.ai.adapters.catalogue_file import PackagedCatalogue
from otlet.ai.adapters.checks_postgres import PostgresChecks
from otlet.ai.adapters.journal_postgres import PostgresCallJournal
from otlet.ai.adapters.ollama import OllamaHost
from otlet.ai.adapters.postgres import PostgresAiSettings
from otlet.ai.adapters.pulls_postgres import PostgresPulls
from otlet.ai.adapters.sealing import PublicKeySealer
from otlet.ai.application.budget import Budget
from otlet.ai.application.models import Models
from otlet.ai.application.settings import AiSettings
from otlet.ai.domain.settings import ProfileEntry, SettingsError
from otlet.collection.adapters.parsing import FeedparserReader, ReadabilityReader
from otlet.collection.adapters.postgres import PostgresCollectionStore
from otlet.collection.application.collection import Collection
from otlet.entrypoints.api import ai, auth, collection, media, triage, watch, workspaces, writing
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.jobs.adapters import procrastinate_queue
from otlet.media.adapters.files_disk import DiskFiles
from otlet.media.adapters.images_pillow import PillowImages
from otlet.media.adapters.postgres import PostgresMediaStore
from otlet.media.application.library import MediaLibrary
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.platform.http import SafeClient
from otlet.watch.adapters.postgres import PostgresWatchStore
from otlet.watch.adapters.triage_postgres import PostgresTriageStore
from otlet.watch.application.triage import Change, Feed
from otlet.watch.application.watch import Watch
from otlet.watch.domain.triage import Decision
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.adapters.articles_postgres import PostgresArticleStore
from otlet.writing.adapters.export_docx import docx
from otlet.writing.adapters.export_pdf import pdf
from otlet.writing.adapters.postgres import PostgresBriefStore
from otlet.writing.application.briefs import Briefs
from otlet.writing.application.drafts import Drafts
from otlet.writing.application.editing import Editing
from otlet.writing.application.exports import Exports
from otlet.writing.domain.brief import BriefError, ModelChoice

logger = logging.getLogger(__name__)


class SinglePageApp(StaticFiles):
    """Static files that fall back to index.html for client-side routes (paths whose last
    segment has no file extension), so reloading /library/42 serves the interface."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Starlette gives the path with the separator of the OS (a backslash on Windows).
            parts = PurePath(path).parts
            is_api = parts[:1] == ("api",)  # an unknown API path stays 404
            if error.status_code != 404 or (parts and "." in parts[-1]) or is_api:
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
    engine = database.create_engine(settings.database_url) if settings.database_url else None

    @app.get("/health")
    def health() -> JSONResponse:
        body: dict[str, str | None] = {"status": "ok", "version": __version__}
        if engine is not None:
            try:
                body["schema_revision"] = database.schema_revision(engine)
                body["database"] = "ok"
            except sa.exc.SQLAlchemyError:
                logger.exception("database unreachable")
                body["status"] = "unavailable"
                body["database"] = "unavailable"
        return JSONResponse(body, status_code=200 if body["status"] == "ok" else 503)

    if engine is not None:
        authentication = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
        auth_router, current_session = auth.build_router(authentication)
        workspace_router, workspace_context = workspaces.build_router(
            Workspaces(PostgresWorkspaceStore(engine)), engine, current_session
        )
        enqueue = procrastinate_queue.enqueuer(settings.require_database_url())
        store = PostgresCollectionStore(engine, enqueue)
        collection_router = collection.build_router(
            Collection(store, SafeClient(), FeedparserReader(), ReadabilityReader()),
            workspace_context,
        )
        watch_router = watch.build_router(
            Watch(PostgresWatchStore(engine, enqueue)), workspace_context
        )
        feed = Feed(PostgresTriageStore(engine))
        triage_router = triage.build_router(feed, workspace_context)
        ai_store = PostgresAiSettings(engine)
        ai_catalogue = PackagedCatalogue().load()
        ai_settings = AiSettings(
            ai_store,
            ai_catalogue,
            PublicKeySealer(settings.secrets_public_key_file),
        )

        def mark_writing(context: WorkspaceContext, item_ids: Sequence[UUID]) -> None:
            feed.change_many(context, list(item_ids), Change(decision=Decision.WRITING))

        def check_model(user_id: UUID, choice: ModelChoice) -> None:
            try:
                ai_settings.check_choice(user_id, ProfileEntry(choice.provider_id, choice.model))
            except SettingsError as error:
                raise BriefError(error.code, str(error)) from error

        brief_store = PostgresBriefStore(engine)
        article_store = PostgresArticleStore(engine, enqueue)
        files_dir = settings.files_dir or settings.run_dir / "files"
        library = MediaLibrary(PostgresMediaStore(engine), DiskFiles(files_dir), PillowImages())

        def media_check(workspace_id: UUID, ids: set[str]) -> set[str]:
            return {str(found) for found in library.existing(workspace_id, map(UUID, ids))}

        def read_image(
            context: WorkspaceContext, media_id: str
        ) -> tuple[bytes, str, int, int] | None:
            found = library.read(context, UUID(media_id))
            return (
                None
                if found is None
                else (found[1], found[0].mime, found[0].width, found[0].height)
            )

        writing_router = writing.build_router(
            Briefs(brief_store, mark_writing, check_model),
            # The API only records a generation: the worker alone calls the models (DR6).
            Drafts(brief_store, article_store),
            Editing(article_store, media_check),
            Exports(article_store, read_image, docx, pdf),
            workspace_context,
        )
        media_router = media.build_router(library, workspace_context)
        ai_router = ai.build_router(
            ai_settings,
            Budget(PostgresBudget(engine)),
            PostgresChecks(engine, enqueue),
            Models(ai_store, ai_catalogue, OllamaHost(), PostgresPulls(engine, enqueue), uuid4),
            PostgresCallJournal(engine),
            authentication,
            current_session,
        )
        routers = [
            auth_router,
            workspace_router,
            collection_router,
            watch_router,
            triage_router,
            ai_router,
            writing_router,
            media_router,
        ]
        for router in routers:
            app.include_router(router)
        # Read by the isolation tests, which check every route of these routers.
        app.state.api_routers = routers
        app.state.current_session = current_session
        app.state.workspace_context = workspace_context

    if settings.ui_dir is not None and settings.ui_dir.is_dir():
        app.mount("/", SinglePageApp(directory=settings.ui_dir, html=True), name="ui")
    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_env())
