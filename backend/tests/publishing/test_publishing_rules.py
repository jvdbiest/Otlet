# SPDX-License-Identifier: AGPL-3.0-or-later
"""The rules of a send (U07, docs/design/PUBLICATION_WORDPRESS.md, ADR-0026)."""

import pytest

from otlet.publishing.domain.model import (
    Action,
    PublishingError,
    check_password,
    check_terms,
    check_url,
    has_marker,
    marker_comment,
    plan,
)


def test_a_draft_never_takes_a_published_post_off_line() -> None:
    assert plan(Action.DRAFT, None) == "draft"
    assert plan(Action.DRAFT, "draft") == "draft"
    assert plan(Action.PUBLISH, None) == "publish"
    assert plan(Action.PUBLISH, "draft") == "publish"
    assert plan(Action.PUBLISH, "publish") == "publish"
    with pytest.raises(PublishingError) as caught:
        plan(Action.DRAFT, "publish")
    assert caught.value.code == "already_published"


def test_a_site_an_application_password_and_terms() -> None:
    assert check_url(" http://192.168.1.5:8080/ ") == "http://192.168.1.5:8080"
    for bad in ("ftp://site", "site.be", "https://user:pw@site.be", "https://site.be/?x=1"):
        with pytest.raises(PublishingError):
            check_url(bad)
    # WordPress shows the application password in groups of four.
    assert check_password("abcd EFGH ijkl MNOP qrst UVWX") == "abcdEFGHijklMNOPqrstUVWX"
    with pytest.raises(PublishingError):
        check_password("short")
    categories, tags = check_terms([3, 3, 5], [" Moto  GP ", "moto gp", "Qatar"])
    assert categories == (3, 5) and tags == ("Moto GP", "Qatar")


def test_the_mark_of_an_article_is_found_in_its_content() -> None:
    key = "0123456789abcdef0123456789abcdef"
    content = f"{marker_comment(key)}\n<p>Texte</p>"
    assert has_marker(content, key)
    assert not has_marker(content, "f" * 32)
    assert not has_marker("<p>otlet</p>", key)
