# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rules of sign-in and sessions, free of any framework (ADR-0029)."""

import hashlib
import hmac
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

PASSWORD_KIND = "password"  # noqa: S105 (identity kind of a local password (ADR-0028))

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

# A session ends after this much inactivity, and in any case after its absolute lifetime.
SESSION_IDLE_TIMEOUT = timedelta(hours=12)
SESSION_LIFETIME = timedelta(days=7)
# last_seen_at is written at most this often, not on every request.
SESSION_TOUCH_INTERVAL = timedelta(minutes=1)
# Sensitive actions require a password typed within this delay (ARCHITECTURE §19.2).
REAUTHENTICATION_VALIDITY = timedelta(minutes=10)

# Failed sign-ins tolerated per window, per login and per client address.
THROTTLE_WINDOW = timedelta(minutes=15)
THROTTLE_MAX_FAILURES_PER_LOGIN = 5
THROTTLE_MAX_FAILURES_PER_CLIENT = 20


class IdentityError(Exception):
    """A rule of the identity module was not met; the message is safe to show."""


class InvalidCredentials(IdentityError):
    """Unknown login, wrong password or disabled account: deliberately indistinguishable."""


class TooManyAttempts(IdentityError):
    def __init__(self, retry_after: timedelta) -> None:
        super().__init__("too many failed attempts")
        self.retry_after = retry_after


class WeakPassword(IdentityError):
    pass


def normalize_login(login: str) -> str:
    """The form stored in user_identities.subject: NFKC, trimmed, lower-case."""
    return unicodedata.normalize("NFKC", login).strip().lower()


def check_password_policy(password: str) -> None:
    length = len(password)
    if length < PASSWORD_MIN_LENGTH:
        raise WeakPassword(f"password must have at least {PASSWORD_MIN_LENGTH} characters")
    if length > PASSWORD_MAX_LENGTH:
        raise WeakPassword(f"password must have at most {PASSWORD_MAX_LENGTH} characters")


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    """Only this digest is stored: a database leak does not leak usable sessions."""
    return hashlib.sha256(token.encode()).digest()


def csrf_token(session_token: str) -> str:
    """Derived from the session token, so it needs no storage and dies with the session."""
    return hashlib.sha256(b"otlet-csrf:" + session_token.encode()).hexdigest()


def csrf_matches(session_token: str, presented: str | None) -> bool:
    return presented is not None and hmac.compare_digest(csrf_token(session_token), presented)


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    user_id: UUID
    created_at: datetime
    last_seen_at: datetime
    reauthenticated_at: datetime
    user_disabled: bool

    def is_valid(self, now: datetime) -> bool:
        return (
            not self.user_disabled
            and now < self.created_at + SESSION_LIFETIME
            and now < self.last_seen_at + SESSION_IDLE_TIMEOUT
        )

    def needs_touch(self, now: datetime) -> bool:
        return now >= self.last_seen_at + SESSION_TOUCH_INTERVAL

    def recently_reauthenticated(self, now: datetime) -> bool:
        return now < self.reauthenticated_at + REAUTHENTICATION_VALIDITY
