# SPDX-License-Identifier: AGPL-3.0-or-later
"""Collection rules of the sites (F-CNF-06, CJ-03, ARCHITECTURE §13.1): robots.txt (RFC 9309)
and the text and data mining reservation of the TDM Reservation Protocol (TDMRep, W3C
community group report), read from /.well-known/tdmrep.json, from the HTTP headers and from the
HTML meta tags.

robots.txt says whether Otlet may fetch a URL at all; the TDM reservation says whether the text
may be mined, here reused to write. A page that may be fetched but whose text is reserved is
kept as "summary only": its title, its link and the summary given by the feed.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from urllib.parse import urlsplit

import protego

from otlet.collection.domain.model import Decision

# The product token Otlet looks for in robots.txt groups (RFC 9309 §2.2.1).
ROBOTS_AGENT = "Otlet"
TDM_RESERVATION = "tdm-reservation"
TDM_POLICY = "tdm-policy"


class RobotsKind(StrEnum):
    """How a site answered for /robots.txt (RFC 9309 §2.3.1)."""

    FOUND = "found"  # 2xx: the rules apply
    MISSING = "missing"  # 4xx: no rules, everything may be fetched
    UNREACHABLE = "unreachable"  # 5xx or network error: assume everything is disallowed


@dataclass(frozen=True, slots=True)
class Robots:
    kind: RobotsKind
    body: str = ""

    def decide(self, url: str) -> Decision:
        if self.kind is RobotsKind.MISSING:
            return Decision(True, "robots_missing")
        if self.kind is RobotsKind.UNREACHABLE:
            return Decision(False, "robots_unreachable")
        if protego.Protego.parse(self.body).can_fetch(url, ROBOTS_AGENT):
            return Decision(True, "robots_allowed")
        return Decision(False, "robots_disallowed", urlsplit(url).path or "/")


def robots_kind(status: int) -> RobotsKind:
    if 200 <= status < 300:
        return RobotsKind.FOUND
    if 400 <= status < 500 and status != 429:
        return RobotsKind.MISSING
    return RobotsKind.UNREACHABLE


@dataclass(frozen=True, slots=True)
class TdmRule:
    location: str
    reserved: bool
    policy: str | None = None

    def matches(self, path: str) -> bool:
        return _pattern(self.location).match(path) is not None


def _pattern(location: str) -> re.Pattern[str]:
    """robots.txt-style path pattern: a prefix, `*` for any sequence, `$` for the end."""
    anchored = location.endswith("$")
    body = location[:-1] if anchored else location
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


def parse_tdmrep(text: str) -> tuple[TdmRule, ...]:
    """The rules of a /.well-known/tdmrep.json file; malformed entries are ignored, and a file
    that is not a JSON list gives no rule."""
    try:
        document = json.loads(text)
    except ValueError:
        return ()
    if not isinstance(document, list):
        return ()
    rules = []
    for entry in document:
        if not isinstance(entry, dict) or not isinstance(entry.get("location"), str):
            continue
        reservation = entry.get(TDM_RESERVATION)
        if reservation not in (0, 1, "0", "1"):
            continue
        policy = entry.get(TDM_POLICY)
        rules.append(
            TdmRule(
                location=entry["location"],
                reserved=str(reservation) == "1",
                policy=policy if isinstance(policy, str) else None,
            )
        )
    return tuple(rules)


def tdm_rule_for(url: str, rules: tuple[TdmRule, ...]) -> TdmRule | None:
    """The first rule whose location matches the path of `url` (TDMRep §3.2)."""
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return next((rule for rule in rules if rule.matches(path)), None)


def header_reservation(headers: dict[str, str]) -> Decision | None:
    """The reservation declared in the HTTP headers of a response, if any."""
    value = headers.get(TDM_RESERVATION, "").strip()
    if value == "1":
        return Decision(False, "tdm_reserved_header", headers.get(TDM_POLICY, ""))
    if value == "0":
        return Decision(True, "tdm_not_reserved_header")
    return None


class _MetaReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = {name.lower(): value or "" for name, value in attrs}
        name = attributes.get("name", "").lower()
        if name in (TDM_RESERVATION, TDM_POLICY) and name not in self.values:
            self.values[name] = attributes.get("content", "").strip()


def meta_reservation(html: str) -> Decision | None:
    """The reservation declared by the meta tags of an HTML page, if any."""
    reader = _MetaReader()
    reader.feed(html)
    value = reader.values.get(TDM_RESERVATION)
    if value == "1":
        return Decision(False, "tdm_reserved_meta", reader.values.get(TDM_POLICY, ""))
    if value == "0":
        return Decision(True, "tdm_not_reserved_meta")
    return None


def file_reservation(url: str, rules: tuple[TdmRule, ...]) -> Decision | None:
    rule = tdm_rule_for(url, rules)
    if rule is None:
        return None
    if rule.reserved:
        return Decision(False, "tdm_reserved_file", rule.policy or "")
    return Decision(True, "tdm_not_reserved_file")


def mining(
    url: str,
    rules: tuple[TdmRule, ...],
    headers: dict[str, str] | None = None,
    html: str | None = None,
) -> Decision:
    """Whether the text at `url` may be used. Any reservation wins: the file of the site, the
    headers of the response, the meta tags of the page; without one, the text may be used."""
    found = [
        file_reservation(url, rules),
        header_reservation(headers or {}),
        meta_reservation(html) if html else None,
    ]
    reserved = next((decision for decision in found if decision and not decision.allowed), None)
    return reserved or Decision(True, "tdm_not_reserved")
