# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rules of sign-in and sessions, without a database (F02)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from otlet.identity.domain import model
from otlet.identity.domain.model import Session

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def session(
    created: timedelta = timedelta(0),
    seen: timedelta = timedelta(0),
    reauthenticated: timedelta = timedelta(0),
    disabled: bool = False,
) -> Session:
    return Session(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        created_at=NOW - created,
        last_seen_at=NOW - seen,
        reauthenticated_at=NOW - reauthenticated,
        user_disabled=disabled,
    )


def test_logins_are_normalised() -> None:
    assert model.normalize_login("  Joël@Example.ORG ") == "joël@example.org"
    # NFKC folds compatibility forms: a full-width letter is the same login.
    assert model.normalize_login("ｊoel@example.org") == "joel@example.org"


@pytest.mark.parametrize("password", ["short", "x" * (model.PASSWORD_MAX_LENGTH + 1)])
def test_password_length_is_bounded(password: str) -> None:
    with pytest.raises(model.WeakPassword):
        model.check_password_policy(password)


def test_a_long_passphrase_is_accepted() -> None:
    model.check_password_policy("correct horse battery staple")


def test_only_a_digest_of_the_token_is_kept() -> None:
    token = model.new_session_token()
    assert len(model.token_hash(token)) == 32
    assert model.token_hash(token) != token.encode()
    assert model.new_session_token() != token


def test_csrf_token_belongs_to_its_session() -> None:
    token, other = model.new_session_token(), model.new_session_token()
    assert model.csrf_matches(token, model.csrf_token(token))
    assert not model.csrf_matches(token, model.csrf_token(other))
    assert not model.csrf_matches(token, None)


def test_a_fresh_session_is_valid() -> None:
    assert session().is_valid(NOW)


def test_a_session_ends_after_inactivity() -> None:
    assert not session(seen=model.SESSION_IDLE_TIMEOUT).is_valid(NOW)


def test_a_session_ends_after_its_lifetime_even_when_active() -> None:
    assert not session(created=model.SESSION_LIFETIME).is_valid(NOW)


def test_a_disabled_account_has_no_session() -> None:
    assert not session(disabled=True).is_valid(NOW)


def test_reauthentication_expires() -> None:
    assert session().recently_reauthenticated(NOW)
    assert not session(reauthenticated=model.REAUTHENTICATION_VALIDITY).recently_reauthenticated(
        NOW
    )


def test_last_seen_is_written_at_most_once_a_minute() -> None:
    assert not session(seen=timedelta(seconds=30)).needs_touch(NOW)
    assert session(seen=model.SESSION_TOUCH_INTERVAL).needs_touch(NOW)
