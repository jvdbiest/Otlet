# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sign-in, sessions and re-authentication (ROADMAP §5.2, ARCHITECTURE §19.2, ADR-0029).

The service depends on two ports: the store (PostgreSQL in production) and the password hasher
(Argon2id). Every rule is decided here or in the domain, never in the HTTP layer.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from otlet.identity.domain import model
from otlet.identity.domain.model import (
    PASSWORD_KIND,
    IdentityError,
    InvalidCredentials,
    Session,
    TooManyAttempts,
)


@dataclass(frozen=True, slots=True)
class Identity:
    id: UUID
    user_id: UUID
    credential: str | None
    user_disabled: bool


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    display_name: str
    is_instance_admin: bool


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, credential: str, password: str) -> bool: ...
    def needs_rehash(self, credential: str) -> bool: ...


class IdentityStore(Protocol):
    def find_identity(self, kind: str, subject: str) -> Identity | None: ...
    def password_identity(self, user_id: UUID) -> Identity | None: ...
    def create_user(
        self, display_name: str, login: str, credential: str, is_instance_admin: bool
    ) -> UUID: ...
    def get_user(self, user_id: UUID) -> User: ...
    def mark_identity_used(self, identity: Identity, now: datetime) -> None: ...
    def replace_credential(self, identity: Identity, credential: str) -> None: ...

    def throttle_failures(self, key: str, window: timedelta) -> int: ...
    def throttle_record_failure(self, key: str, window: timedelta) -> int: ...
    def throttle_clear(self, key: str) -> None: ...

    def create_session(
        self, user_id: UUID, token_hash: bytes, now: datetime, user_agent: str | None
    ) -> Session: ...
    def find_session(self, token_hash: bytes) -> Session | None: ...
    def touch_session(self, session: Session, now: datetime) -> None: ...
    def mark_reauthenticated(self, session: Session, now: datetime) -> None: ...
    def delete_session(self, session: Session) -> None: ...
    def delete_other_sessions(self, session: Session) -> None: ...


class ReauthenticationRequired(IdentityError):
    def __init__(self) -> None:
        super().__init__("reauthentication required")


@dataclass(frozen=True, slots=True)
class SignedIn:
    token: str
    session: Session


def utcnow() -> datetime:
    return datetime.now(UTC)


class Authentication:
    def __init__(
        self,
        store: IdentityStore,
        hasher: PasswordHasher,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._store = store
        self._hasher = hasher
        self._clock = clock
        # Verified when the login is unknown, so that both answers take the same time.
        self._decoy = hasher.hash(model.new_session_token())

    def create_user(
        self, display_name: str, login: str, password: str, *, is_instance_admin: bool = False
    ) -> UUID:
        model.check_password_policy(password)
        return self._store.create_user(
            display_name.strip(),
            model.normalize_login(login),
            self._hasher.hash(password),
            is_instance_admin,
        )

    def sign_in(
        self, login: str, password: str, client: str, user_agent: str | None = None
    ) -> SignedIn:
        subject = model.normalize_login(login)
        keys = (f"login:{subject}", f"client:{client}")
        limits = (model.THROTTLE_MAX_FAILURES_PER_LOGIN, model.THROTTLE_MAX_FAILURES_PER_CLIENT)
        for key, limit in zip(keys, limits, strict=True):
            if self._store.throttle_failures(key, model.THROTTLE_WINDOW) >= limit:
                raise TooManyAttempts(model.THROTTLE_WINDOW)

        identity = self._store.find_identity(PASSWORD_KIND, subject)
        if identity is None or identity.credential is None:
            self._hasher.verify(self._decoy, password)
            verified = False
        else:
            verified = self._hasher.verify(identity.credential, password)
        if identity is None or identity.credential is None or not verified:
            for key in keys:
                self._store.throttle_record_failure(key, model.THROTTLE_WINDOW)
            raise InvalidCredentials("invalid login or password")
        if identity.user_disabled:
            raise InvalidCredentials("invalid login or password")

        self._store.throttle_clear(keys[0])
        now = self._clock()
        if self._hasher.needs_rehash(identity.credential):
            self._store.replace_credential(identity, self._hasher.hash(password))
        self._store.mark_identity_used(identity, now)
        token = model.new_session_token()
        session = self._store.create_session(
            identity.user_id, model.token_hash(token), now, user_agent
        )
        return SignedIn(token=token, session=session)

    def resolve(self, token: str) -> Session | None:
        """The live session behind a cookie, or None. An expired session is deleted."""
        session = self._store.find_session(model.token_hash(token))
        if session is None:
            return None
        now = self._clock()
        if not session.is_valid(now):
            self._store.delete_session(session)
            return None
        if session.needs_touch(now):
            self._store.touch_session(session, now)
        return session

    def user(self, session: Session) -> User:
        return self._store.get_user(session.user_id)

    def sign_out(self, session: Session) -> None:
        self._store.delete_session(session)

    def reauthenticate(self, session: Session, password: str) -> None:
        identity = self._store.password_identity(session.user_id)
        if (
            identity is None
            or identity.credential is None
            or not self._hasher.verify(identity.credential, password)
        ):
            raise InvalidCredentials("invalid password")
        self._store.mark_reauthenticated(session, self._clock())

    def require_recent_reauthentication(self, session: Session) -> None:
        if not session.recently_reauthenticated(self._clock()):
            raise ReauthenticationRequired

    def change_password(self, session: Session, new_password: str) -> None:
        """Replaces the password and ends every other session of the account."""
        self.require_recent_reauthentication(session)
        model.check_password_policy(new_password)
        identity = self._store.password_identity(session.user_id)
        if identity is None:
            raise InvalidCredentials("this account has no password")
        self._store.replace_credential(identity, self._hasher.hash(new_password))
        self._store.delete_other_sessions(session)
