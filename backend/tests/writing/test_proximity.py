# SPDX-License-Identifier: AGPL-3.0-or-later
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from otlet.workspaces.domain.model import Role, WorkspaceContext
from otlet.writing.application.exports import Exports
from otlet.writing.application.library import Library
from otlet.writing.application.proximity import JustificationError, override, run_check
from otlet.writing.domain.proximity import (
    OTHER_LANGUAGE,
    SAME_LANGUAGE,
    Encode,
    Gate,
    Source,
    TooClose,
    check,
    common_subsequence,
    gate_of,
    lexical_score,
    sentences,
)


def encoder(known: dict[str, list[float]]) -> Encode:
    """Each sentence gets the unit vector its first word names; others are orthogonal to all."""

    def encode(texts: Sequence[str]) -> list[list[float]]:
        return [known.get(text.split()[0].strip(".,"), [0.0, 0.0, 1.0]) for text in texts]

    return encode


def text_of(*firsts: str) -> str:
    return " ".join(f"{first} dit quelque chose ici." for first in firsts)


def _draft(*firsts: str) -> list[str]:
    return [text_of(*firsts)]


def test_common_subsequence_counts_words_in_order() -> None:
    assert common_subsequence(["a", "b", "c", "d"], ["a", "c", "d"]) == 3
    assert common_subsequence(["a", "b"], ["b", "a"]) == 1
    assert common_subsequence([], ["a"]) == 0
    assert common_subsequence(["a"], []) == 0
    assert common_subsequence(list("abcbdab"), list("bdcaba")) == 4


def test_lexical_score_is_over_the_text_checked() -> None:
    assert lexical_score("Le chat dort sur le toit", "le chat dort") == 1.0
    assert lexical_score("Rien de commun", "tout autre chose") == 0.0
    assert lexical_score("Peu importe", "") == 0.0


def test_sentences_split_after_a_final_mark_before_a_capital() -> None:
    found = sentences("Une phrase. Une autre! encore ici. Fin")
    assert found == ["Une phrase.", "Une autre! encore ici.", "Fin"]


def test_a_passage_taken_from_a_source_is_not_diluted_by_the_rest() -> None:
    near = {"Proche": [1.0, 0.0, 0.0], "Autre": [0.0, 1.0, 0.0]}
    firsts = ["Proche"] * 5 + ["Rien"] * 15
    source = Source("Proche", None, "fr", text_of("Proche", "Proche"))
    report = check("Titre", _draft(*firsts), "fr", [source], encoder(near))
    assert report["blocked"] is True
    found = report["sources"][0]
    assert found["score"] == 1.0
    assert found["limit"] == SAME_LANGUAGE
    assert found["passages"]
    assert found["passages"][0]["cosine"] == 1.0
    assert found["passages"][0]["paragraph"].startswith("Proche dit")


def test_an_independent_text_passes() -> None:
    near = {"Proche": [1.0, 0.0, 0.0], "Autre": [0.0, 1.0, 0.0]}
    source = Source("Autre", None, "fr", text_of("Autre", "Autre"))
    report = check("Titre", _draft(*["Proche"] * 8), "fr", [source], encoder(near))
    assert report["blocked"] is False
    assert report["sources"][0]["too_close"] is False
    assert report["sources"][0]["passages"] == []


def test_another_language_has_its_own_limit_and_no_lexical_score() -> None:
    near = {"Proche": [1.0, 0.0, 0.0], "Close": [0.81, 0.586, 0.0]}
    source = Source("Close", None, "en", text_of("Close", "Close"))
    report = check("Titre", _draft(*["Proche"] * 8), "fr-BE", [source], encoder(near))
    found = report["sources"][0]
    assert found["languages"] == "other"
    assert found["limit"] == OTHER_LANGUAGE
    assert found["lexical"] == 0.0
    assert report["blocked"] is True


def test_same_words_block_even_with_a_low_semantic_score() -> None:
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    source = Source("Titre", None, "fr", words)

    def far_apart(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] if index % 2 else [0.0, 1.0] for index, _ in enumerate(texts)]

    report = check("Titre", [words], "fr", [source], far_apart)
    assert report["sources"][0]["lexical"] >= 0.70
    assert report["blocked"] is True


def test_the_references_of_a_draft_are_not_read() -> None:
    seen: list[str] = []

    def encode(texts: Sequence[str]) -> list[list[float]]:
        seen.extend(texts)
        return [[1.0] for _ in texts]

    check("Titre", ["Une phrase [1] [2]."], "fr", [Source("S", None, "fr", "Texte.")], encode)
    assert not any("[1]" in text for text in seen)


@pytest.mark.parametrize(
    ("has_brief", "proximity", "override", "gate"),
    [
        (False, None, None, "open"),
        (True, None, None, "pending"),
        (True, {"blocked": False}, None, "open"),
        (True, {"blocked": True}, None, "blocked"),
        (True, {"blocked": True}, {"reason": "ma source"}, "open"),
        (True, {"status": "failed", "blocked": False}, None, "open"),
    ],
)
def test_gate(
    has_brief: bool, proximity: dict[str, Any] | None, override: dict[str, Any] | None, gate: str
) -> None:
    assert gate_of(has_brief, proximity, override) == gate


CONTEXT = WorkspaceContext(uuid4(), uuid4(), Role.OWNER)


class Store:
    """A store with one version to check, as the worker sees it."""

    def __init__(self) -> None:
        self.saved: dict[str, Any] | None = None
        self.reason: str | None = None

    def gate(self, workspace_id: UUID, article_id: UUID, number: int) -> Gate:
        return "pending"

    def to_check(
        self, workspace_id: UUID, article_id: UUID, number: int
    ) -> tuple[str, dict[str, Any], list[Source]] | None:
        if self.saved is not None:
            return None
        paragraph = {"type": "paragraph", "content": [{"type": "text", "text": "Une phrase."}]}
        document = {"attrs": {"langue": "fr"}, "content": [paragraph]}
        return "Titre", document, [Source("S", None, "fr", "Une phrase.")]

    def save_proximity(
        self, workspace_id: UUID, article_id: UUID, number: int, report: dict[str, Any]
    ) -> None:
        self.saved = report

    def override_proximity(
        self, workspace_id: UUID, user_id: UUID, article_id: UUID, number: int, reason: str
    ) -> bool:
        self.reason = reason
        return True


def test_the_job_keeps_the_report_and_does_not_load_the_model_twice() -> None:
    store = Store()
    loads: list[int] = []

    def encoder() -> Encode:
        loads.append(1)
        return lambda texts: [[1.0] for _ in texts]

    run_check(store, encoder, uuid4(), uuid4(), 1)
    assert store.saved is not None
    assert store.saved["status"] == "checked"
    run_check(store, encoder, uuid4(), uuid4(), 1)
    assert len(loads) == 1


def test_a_check_that_fails_says_so_and_blocks_nothing() -> None:
    store = Store()

    def encoder() -> Encode:
        raise RuntimeError("no model")

    run_check(store, encoder, uuid4(), uuid4(), 1)
    assert store.saved == {"status": "failed", "blocked": False, "sources": []}
    assert gate_of(True, store.saved, None) == "open"


def test_a_justification_is_required_and_folded() -> None:
    store = Store()
    with pytest.raises(JustificationError):
        override(store, CONTEXT, uuid4(), 1, "  court  ")
    assert override(store, CONTEXT, uuid4(), 1, "  source   sous licence  ") is True
    assert store.reason == "source sous licence"


@pytest.mark.parametrize("gate", ["blocked", "pending"])
def test_nothing_is_validated_nor_exported_past_the_gate(gate: Gate) -> None:
    version = cast(Any, SimpleNamespace(title="Titre", document={}))
    versions = cast(Any, SimpleNamespace(version=lambda *_: version, send=lambda *_: True))

    def writer(*_: Any) -> bytes:
        return b""

    with pytest.raises(TooClose) as sent:
        Library(versions, lambda *_: gate).send(CONTEXT, uuid4(), 1)
    assert sent.value.gate == gate
    exports = Exports(versions, lambda *_: None, writer, writer, lambda *_: gate)
    with pytest.raises(TooClose):
        exports.export(CONTEXT, uuid4(), 1, "txt")
    with pytest.raises(TooClose):
        exports.export_many(CONTEXT, [(uuid4(), 1)], "txt")
