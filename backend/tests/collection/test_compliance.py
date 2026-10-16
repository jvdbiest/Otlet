# SPDX-License-Identifier: AGPL-3.0-or-later
"""robots.txt and the TDM reservation decide what Otlet may fetch and use (U01, F-CNF-06,
CJ-03)."""

import pytest

from otlet.collection.domain import compliance
from otlet.collection.domain.compliance import Robots, RobotsKind, TdmRule

ROBOTS = """
User-agent: *
Disallow: /private/

User-agent: Otlet
Disallow: /no-otlet/
Allow: /
"""


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (200, RobotsKind.FOUND),
        (404, RobotsKind.MISSING),
        (403, RobotsKind.MISSING),
        (429, RobotsKind.UNREACHABLE),
        (500, RobotsKind.UNREACHABLE),
        (503, RobotsKind.UNREACHABLE),
    ],
)
def test_robots_status_follows_rfc_9309(status: int, kind: RobotsKind) -> None:
    assert compliance.robots_kind(status) is kind


def test_the_otlet_group_applies_to_otlet() -> None:
    robots = Robots(RobotsKind.FOUND, ROBOTS)
    assert robots.decide("https://example.org/news/1").allowed
    # The group for Otlet replaces the * group: /private/ is not closed to it.
    assert robots.decide("https://example.org/private/1").allowed
    refused = robots.decide("https://example.org/no-otlet/feed.xml")
    assert (refused.allowed, refused.reason) == (False, "robots_disallowed")


def test_missing_robots_allows_and_unreachable_robots_refuses() -> None:
    assert Robots(RobotsKind.MISSING).decide("https://example.org/feed").allowed
    unreachable = Robots(RobotsKind.UNREACHABLE).decide("https://example.org/feed")
    assert (unreachable.allowed, unreachable.reason) == (False, "robots_unreachable")


TDMREP = """[
  {"location": "/open/*", "tdm-reservation": 0},
  {"location": "/news/*", "tdm-reservation": 1, "tdm-policy": "https://example.org/tdm.json"},
  {"location": "/", "tdm-reservation": 0},
  {"location": 42, "tdm-reservation": 1},
  {"location": "/broken", "tdm-reservation": "maybe"}
]"""


def test_tdmrep_rules_are_parsed_and_malformed_ones_ignored() -> None:
    rules = compliance.parse_tdmrep(TDMREP)
    assert rules == (
        TdmRule("/open/*", reserved=False),
        TdmRule("/news/*", reserved=True, policy="https://example.org/tdm.json"),
        TdmRule("/", reserved=False),
    )


@pytest.mark.parametrize("text", ["", "not json", "{}", '{"location": "/"}', "null"])
def test_a_file_that_is_not_a_list_has_no_rule(text: str) -> None:
    assert compliance.parse_tdmrep(text) == ()


def test_the_first_matching_rule_applies() -> None:
    rules = compliance.parse_tdmrep(TDMREP)
    reserved = compliance.file_reservation("https://example.org/news/2026/10/a", rules)
    assert reserved is not None
    assert (reserved.allowed, reserved.reason, reserved.detail) == (
        False,
        "tdm_reserved_file",
        "https://example.org/tdm.json",
    )
    opened = compliance.file_reservation("https://example.org/open/news/a", rules)
    assert opened is not None and opened.allowed
    assert compliance.file_reservation("https://example.org/blog", ()) is None


def test_location_patterns_follow_robots_syntax() -> None:
    assert TdmRule("/a/*.pdf$", True).matches("/a/b/c.pdf")
    assert not TdmRule("/a/*.pdf$", True).matches("/a/b/c.pdf?x=1")
    assert TdmRule("/a", True).matches("/abc")
    assert not TdmRule("/a", True).matches("/b/a")


def test_headers_and_meta_tags_declare_a_reservation() -> None:
    header = compliance.header_reservation({"tdm-reservation": "1", "tdm-policy": "https://p"})
    assert header is not None and (header.allowed, header.reason) == (False, "tdm_reserved_header")
    page = '<html><head><meta name="TDM-Reservation" content="1"></head><body></body></html>'
    meta = compliance.meta_reservation(page)
    assert meta is not None and (meta.allowed, meta.reason) == (False, "tdm_reserved_meta")
    assert compliance.meta_reservation("<p>no meta</p>") is None
    assert compliance.header_reservation({}) is None


def test_any_reservation_wins() -> None:
    open_file = (TdmRule("/", reserved=False),)
    page = '<meta name="tdm-reservation" content="1">'
    assert not compliance.mining("https://example.org/a", open_file, html=page).allowed
    assert not compliance.mining(
        "https://example.org/a", open_file, headers={"tdm-reservation": "1"}
    ).allowed
    free = compliance.mining("https://example.org/a", open_file, {"tdm-reservation": "0"}, "<p/>")
    assert free.allowed
