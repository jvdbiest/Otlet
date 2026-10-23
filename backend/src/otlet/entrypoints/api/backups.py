# SPDX-License-Identifier: AGPL-3.0-or-later
"""Réglages › Sauvegardes (F08, ADR-0042), for the administrator of the instance: the state of
the destination and of the service, the schedule, « Sauvegarder maintenant », the list of the
backups and their download. The API never takes nor restores a backup itself: the backup service
does, with rights the API does not have."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from otlet.backup.adapters.archive import tar_stream
from otlet.backup.application.backups import BackupError, Catalog
from otlet.backup.application.service import Control, Request
from otlet.backup.domain.backup import Manifest, Schedule
from otlet.entrypoints.api.auth import same_origin
from otlet.identity.application.authentication import Authentication
from otlet.identity.domain.model import Session

PREFIX = "/api/admin/backups"


class ScheduleView(BaseModel):
    enabled: bool
    hour_utc: int = Field(ge=0, le=23)
    daily: int = Field(ge=1, le=60)
    weekly: int = Field(ge=0, le=52)


class StateView(BaseModel):
    configured: bool  # a destination is mounted for the API to read
    checked_at: str | None
    writable: bool
    free_bytes: int | None
    total_bytes: int | None
    error: str | None
    running: bool
    last_name: str | None
    last_error: str | None
    encrypted: bool


class RequestView(BaseModel):
    requested_at: str
    status: Literal["pending", "running", "done", "failed"]
    name: str | None
    error: str | None


class BackupView(BaseModel):
    name: str
    created_at: str
    reason: str
    verified: bool
    problems: list[str]
    encrypted: bool
    secrets: bool
    database_bytes: int
    files: int
    files_bytes: int
    files_new: int
    schema_revision: str
    totals: dict[str, int]  # rows by block, all workspaces

    @classmethod
    def of(cls, name: str, manifest: Manifest) -> "BackupView":
        return cls(
            name=name,
            created_at=manifest.created_at,
            reason=manifest.reason,
            verified=manifest.verified,
            problems=list(manifest.problems),
            encrypted=manifest.encrypted,
            secrets=manifest.secrets,
            database_bytes=manifest.database_bytes,
            files=manifest.files,
            files_bytes=manifest.files_bytes,
            files_new=manifest.files_new,
            schema_revision=manifest.schema_revision,
            totals={block: sum(rows.values()) for block, rows in manifest.counts.items()},
        )


class BackupsView(BaseModel):
    schedule: ScheduleView
    state: StateView
    request: RequestView | None
    backups: list[BackupView]


def build_router(
    control: Control,
    destination: Path | None,
    auth: Authentication,
    current_session: Callable[..., Session],
) -> APIRouter:
    CurrentSession = Annotated[Session, Depends(current_session)]
    router = APIRouter(prefix=PREFIX, dependencies=[Depends(same_origin)])

    def admin(session: Session) -> None:
        if not auth.user(session).is_instance_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")

    def catalog() -> Catalog | None:
        return None if destination is None else Catalog(destination)

    @router.get("")
    def overview(session: CurrentSession) -> BackupsView:
        """The backups of the instance, the state of their destination, their schedule."""
        admin(session)
        schedule = control.schedule()
        state = control.state()
        request = control.request()
        found = catalog()
        backups = []
        if found is not None:
            for name in found.names():
                try:
                    backups.append(BackupView.of(name, found.manifest(name)))
                except (BackupError, ValueError, OSError):
                    continue  # a folder being removed, or not readable: not listed
        return BackupsView(
            schedule=ScheduleView(
                enabled=schedule.enabled,
                hour_utc=schedule.hour_utc,
                daily=schedule.daily,
                weekly=schedule.weekly,
            ),
            state=StateView(
                configured=destination is not None,
                checked_at=state.checked_at,
                writable=state.writable,
                free_bytes=state.free_bytes,
                total_bytes=state.total_bytes,
                error=state.error,
                running=state.running,
                last_name=state.last_name,
                last_error=state.last_error,
                encrypted=state.encrypted,
            ),
            request=None
            if request is None
            else RequestView(
                requested_at=request.requested_at,
                status=request.status,
                name=request.name,
                error=request.error,
            ),
            backups=backups,
        )

    @router.put("/schedule")
    def set_schedule(body: ScheduleView, session: CurrentSession) -> ScheduleView:
        """When the daily backup runs, and how many are kept."""
        admin(session)
        control.save_schedule(Schedule(body.enabled, body.hour_utc, body.daily, body.weekly))
        return body

    @router.post("/run", status_code=status.HTTP_202_ACCEPTED)
    def run_now(session: CurrentSession) -> RequestView:
        """« Sauvegarder maintenant »: the backup service takes it within half a minute. 409
        `already_running` while one is waiting or running."""
        admin(session)
        current = control.request()
        if current is not None and current.status in ("pending", "running"):
            raise HTTPException(status.HTTP_409_CONFLICT, "already_running")
        request = Request(
            requested_at=datetime.now(UTC).isoformat(),
            requested_by=str(session.user_id),
            status="pending",
        )
        control.save_request(request)
        return RequestView(
            requested_at=request.requested_at, status="pending", name=None, error=None
        )

    @router.get(
        "/{name}/download",
        response_class=StreamingResponse,
        responses={200: {"content": {"application/x-tar": {}}}},
    )
    def download(name: str, session: CurrentSession) -> StreamingResponse:
        """A backup as one .tar file, written as it is sent. Encrypted backups stay encrypted:
        only their passphrase opens them."""
        admin(session)
        found = catalog()
        if found is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "backup_not_found")
        try:
            folder = found.folder(name)
        except BackupError as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "backup_not_found") from error
        return StreamingResponse(
            tar_stream(folder),
            media_type="application/x-tar",
            headers={
                "Content-Disposition": f'attachment; filename="otlet-{name}.tar"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    return router
