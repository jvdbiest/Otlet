# SPDX-License-Identifier: AGPL-3.0-or-later
"""Routes of the AI settings (F05, ADR-0027): what the instance offers, the providers and the
profile of the signed-in user, and the policy of the instance, changed by its administrator.

Keys go in, never out: a provider shows only the last characters of its key."""

import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from otlet.ai.application.budget import Budget
from otlet.ai.application.checks import Check, CheckStore
from otlet.ai.application.models import Installed, Models, Pull
from otlet.ai.application.settings import AiSettings
from otlet.ai.domain.budget import LIMIT_MAX
from otlet.ai.domain.settings import (
    ENDPOINT_MAX_LENGTH,
    KEY_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PROFILE_MAX,
    InstancePolicy,
    ProfileEntry,
    Provider,
    SettingsError,
)
from otlet.entrypoints.api.auth import same_origin
from otlet.identity.application.authentication import Authentication
from otlet.identity.domain.model import Session
from otlet.platform.secrets import SecretError

PREFIX = "/api/ai"


class CallJournalReader(Protocol):
    def recent(self, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]: ...


class KindView(BaseModel):
    name: str
    label: str
    endpoint: str
    api_key: bool
    custom_models: bool


class ModelView(BaseModel):
    provider: str
    model: str
    status: Literal["tested", "untested", "blocked"]
    paid: bool
    local: bool
    context: int
    price_in: Decimal
    price_out: Decimal


class CatalogueView(BaseModel):
    currency: str
    kinds: list[KindView]
    models: list[ModelView]


class ProviderView(BaseModel):
    id: UUID
    name: str
    kind: str
    endpoint: str
    key_hint: str | None
    created_at: datetime
    context_window: int | None  # None: automatic

    @classmethod
    def of(cls, provider: Provider) -> "ProviderView":
        return cls(
            id=provider.id,
            name=provider.name,
            kind=provider.kind,
            endpoint=provider.endpoint,
            key_hint=provider.key_hint,
            created_at=provider.created_at,
            context_window=provider.context_window,
        )


class NewProvider(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    kind: str = Field(min_length=1, max_length=40)
    endpoint: str | None = Field(default=None, max_length=ENDPOINT_MAX_LENGTH)
    api_key: str | None = Field(default=None, max_length=KEY_MAX_LENGTH)


class ProviderChanges(BaseModel):
    """`api_key` is taken into account only with `replace_key`: an empty field of the form keeps
    the key, which the interface never receives."""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    endpoint: str = Field(min_length=1, max_length=ENDPOINT_MAX_LENGTH)
    api_key: str | None = Field(default=None, max_length=KEY_MAX_LENGTH)
    replace_key: bool = False


class ProfileEntryView(BaseModel):
    provider_id: UUID
    model: str = Field(min_length=1, max_length=200)


class ProfileView(BaseModel):
    entries: list[ProfileEntryView] = Field(max_length=PROFILE_MAX)


class ContextWindowBody(BaseModel):
    """None: automatic (the window of each model from the catalogue, 4,096 for a local engine)."""

    context_window: int | None = None


class PolicyView(BaseModel):
    allowed_paid: list[str] = Field(default_factory=list, max_length=50)
    local_networks: list[str] = Field(default_factory=list, max_length=20)
    local_ports: list[int] = Field(default_factory=list, max_length=20)
    allow_model_install: bool = False

    @classmethod
    def of(cls, policy: InstancePolicy) -> "PolicyView":
        return cls(
            allowed_paid=sorted(policy.allowed_paid),
            local_networks=list(policy.local_networks),
            local_ports=list(policy.local_ports),
            allow_model_install=policy.allow_model_install,
        )


class InstalledModelView(BaseModel):
    name: str
    size: int  # bytes


class InstalledView(BaseModel):
    models: list[InstalledModelView]
    can_install: bool  # the administrator allows installing models

    @classmethod
    def of(cls, installed: Installed) -> "InstalledView":
        return cls(
            models=[InstalledModelView(name=m.name, size=m.size) for m in installed.models],
            can_install=installed.can_install,
        )


class PullBody(BaseModel):
    model: str = Field(min_length=1, max_length=100)


class PullView(BaseModel):
    id: UUID
    provider_id: UUID
    model: str
    status: Literal["running", "done", "failed"]
    step: str
    completed: int
    total: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, pull: Pull) -> "PullView":
        return cls(
            id=pull.id,
            provider_id=pull.provider_id,
            model=pull.model,
            status=pull.status,
            step=pull.step,
            completed=pull.completed,
            total=pull.total,
            error=pull.error,
            created_at=pull.created_at,
            finished_at=pull.finished_at,
        )


class BudgetView(BaseModel):
    month: date
    currency: str
    limit: Decimal
    spent: Decimal
    reserved: Decimal
    usable: Decimal


class NewLimit(BaseModel):
    monthly_limit: Decimal = Field(ge=0, le=LIMIT_MAX)


class ProfileCheckView(BaseModel):
    id: UUID
    created_at: datetime
    finished_at: datetime | None
    result: dict[str, Any] | None

    @classmethod
    def of(cls, check: Check) -> "ProfileCheckView":
        return cls(
            id=check.id,
            created_at=check.created_at,
            finished_at=check.finished_at,
            result=check.result,
        )


class CallView(BaseModel):
    usage: str
    provider_kind: str
    model: str
    result: str
    detail: str
    tokens_in: int
    tokens_out: int
    cost: Decimal
    seconds: Decimal
    at: datetime


def _refused(error: SettingsError) -> HTTPException:
    codes = {
        "name_taken": status.HTTP_409_CONFLICT,
        "admin_only": status.HTTP_403_FORBIDDEN,
        "install_not_allowed": status.HTTP_403_FORBIDDEN,
        "engine_unreachable": status.HTTP_502_BAD_GATEWAY,
    }
    return HTTPException(codes.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT), error.code)


def _cents(amount: Decimal) -> Decimal:
    """An amount as people read it: the reservations compute with more decimals."""
    return amount.quantize(Decimal("0.01"))


def _no_key() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "secrets_unavailable")


def build_router(
    settings: AiSettings,
    budget: Budget,
    checks: CheckStore,
    models: Models,
    journal: CallJournalReader,
    auth: Authentication,
    current_session: Callable[..., Session],
) -> APIRouter:
    CurrentSession = Annotated[Session, Depends(current_session)]
    router = APIRouter(prefix=PREFIX, dependencies=[Depends(same_origin)])

    @router.get("/catalogue")
    def catalogue(session: CurrentSession) -> CatalogueView:
        catalogue = settings.catalogue
        return CatalogueView(
            currency=catalogue.currency,
            kinds=[
                KindView(
                    name=kind.name,
                    label=kind.label,
                    endpoint=kind.endpoint,
                    api_key=kind.api_key,
                    custom_models=kind.custom_models,
                )
                for kind in catalogue.kinds
            ],
            models=[
                ModelView(
                    provider=offered.entry.provider,
                    model=offered.entry.model,
                    status=offered.status.value,
                    paid=offered.entry.paid,
                    local=offered.entry.local,
                    context=offered.entry.context,
                    price_in=offered.entry.price_in,
                    price_out=offered.entry.price_out,
                )
                for offered in settings.offered()
            ],
        )

    @router.get("/providers")
    def list_providers(session: CurrentSession) -> list[ProviderView]:
        return [ProviderView.of(p) for p in settings.providers(session.user_id)]

    @router.post("/providers", status_code=status.HTTP_201_CREATED)
    def add_provider(body: NewProvider, session: CurrentSession) -> ProviderView:
        try:
            provider = settings.add_provider(
                session.user_id,
                name=body.name,
                kind=body.kind,
                endpoint=body.endpoint,
                api_key=body.api_key,
            )
        except SettingsError as error:
            raise _refused(error) from error
        except SecretError as error:
            raise _no_key() from error
        return ProviderView.of(provider)

    @router.put("/providers/{provider_id}")
    def update_provider(
        provider_id: UUID, body: ProviderChanges, session: CurrentSession
    ) -> ProviderView:
        try:
            provider = settings.update_provider(
                session.user_id,
                provider_id,
                name=body.name,
                endpoint=body.endpoint,
                api_key=body.api_key,
                replace_key=body.replace_key,
            )
        except SettingsError as error:
            raise _refused(error) from error
        except SecretError as error:
            raise _no_key() from error
        if provider is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "provider_not_found")
        return ProviderView.of(provider)

    @router.get("/providers/{provider_id}/models")
    def installed_models(provider_id: UUID, session: CurrentSession) -> InstalledView:
        """The models installed on the local engine of a provider (Ollama), read from the engine."""
        try:
            return InstalledView.of(models.installed(session.user_id, provider_id))
        except SettingsError as error:
            raise _refused(error) from error

    @router.post("/providers/{provider_id}/pulls", status_code=status.HTTP_202_ACCEPTED)
    def start_pull(provider_id: UUID, body: PullBody, session: CurrentSession) -> PullView:
        """Has the local engine download a model, if the administrator allows it; follow it
        with `/pulls/{pull_id}`."""
        try:
            return PullView.of(models.start_pull(session.user_id, provider_id, body.model))
        except SettingsError as error:
            raise _refused(error) from error

    @router.get("/pulls/{pull_id}")
    def get_pull(pull_id: UUID, session: CurrentSession) -> PullView:
        pull = models.get_pull(session.user_id, pull_id)
        if pull is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "pull_not_found")
        return PullView.of(pull)

    @router.put("/providers/{provider_id}/context-window")
    def set_context_window(
        provider_id: UUID, body: ContextWindowBody, session: CurrentSession
    ) -> ProviderView:
        """The context window of the provider's models: automatic, or the number of tokens the
        user set (a local engine's depends on its machine)."""
        try:
            provider = settings.set_context_window(
                session.user_id, provider_id, body.context_window
            )
        except SettingsError as error:
            raise _refused(error) from error
        if provider is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "provider_not_found")
        return ProviderView.of(provider)

    @router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_provider(provider_id: UUID, session: CurrentSession) -> None:
        if not settings.delete_provider(session.user_id, provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "provider_not_found")

    @router.get("/profile")
    def get_profile(session: CurrentSession) -> ProfileView:
        profile = settings.profile(session.user_id)
        return ProfileView(
            entries=[
                ProfileEntryView(provider_id=e.provider_id, model=e.model) for e in profile.entries
            ]
        )

    @router.put("/profile")
    def set_profile(body: ProfileView, session: CurrentSession) -> ProfileView:
        try:
            profile = settings.set_profile(
                session.user_id, [ProfileEntry(e.provider_id, e.model) for e in body.entries]
            )
        except SettingsError as error:
            raise _refused(error) from error
        return ProfileView(
            entries=[
                ProfileEntryView(provider_id=e.provider_id, model=e.model) for e in profile.entries
            ]
        )

    def budget_view(user_id: UUID) -> BudgetView:
        state = budget.state(user_id)
        return BudgetView(
            month=state.month,
            currency=settings.catalogue.currency,
            limit=_cents(state.limit),
            spent=_cents(state.spent),
            reserved=_cents(state.reserved),
            usable=_cents(state.usable),
        )

    @router.get("/budget")
    def get_budget(session: CurrentSession) -> BudgetView:
        return budget_view(session.user_id)

    @router.put("/budget")
    def set_budget(body: NewLimit, session: CurrentSession) -> BudgetView:
        budget.set_limit(session.user_id, body.monthly_limit)
        return budget_view(session.user_id)

    @router.post("/checks", status_code=status.HTTP_202_ACCEPTED)
    def start_check(session: CurrentSession) -> ProfileCheckView:
        """« Tester » : one small structured answer through the profile, by the worker."""
        return ProfileCheckView.of(checks.create(session.user_id, uuid.uuid4()))

    @router.get("/checks/{check_id}")
    def get_check(check_id: UUID, session: CurrentSession) -> ProfileCheckView:
        check = checks.get(session.user_id, check_id)
        if check is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "check_not_found")
        return ProfileCheckView.of(check)

    @router.get("/calls")
    def recent_calls(session: CurrentSession) -> list[CallView]:
        """The last calls of the user: result, tokens, cost and duration, never the content."""
        return [CallView(**call) for call in journal.recent(session.user_id)]

    @router.get("/policy")
    def get_policy(session: CurrentSession) -> PolicyView:
        return PolicyView.of(settings.policy())

    @router.put("/policy")
    def set_policy(body: PolicyView, session: CurrentSession) -> PolicyView:
        try:
            policy = settings.set_policy(
                is_admin=auth.user(session).is_instance_admin,
                allowed_paid=body.allowed_paid,
                networks=body.local_networks,
                ports=body.local_ports,
                allow_model_install=body.allow_model_install,
            )
        except SettingsError as error:
            raise _refused(error) from error
        return PolicyView.of(policy)

    return router
