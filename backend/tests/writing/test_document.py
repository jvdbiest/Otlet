# SPDX-License-Identifier: AGPL-3.0-or-later
"""« Document plateforme v1 » as the editor sends it (X03, ADR-0036): checked, its blocks'
origin worked out, rendered to the HTML the editor reproduces."""

from typing import Any

from otlet.writing.domain.document import check, render, with_origins

SOURCES = [{"id": "S1", "titre": "Le journal", "url": "https://journal.example.org/1"}]


def text(value: str, *marks: dict[str, Any]) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": value}
    if marks:
        node["marks"] = list(marks)
    return node


def paragraph(
    *content: dict[str, Any], id: str | None = "b1", origine: str = "ia"
) -> dict[str, Any]:
    return {"type": "paragraph", "attrs": {"id": id, "origine": origine}, "content": list(content)}


def doc(*blocks: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "doc",
        "attrs": {"version_schema": 1, "langue": "fr", "sources": SOURCES},
        "content": list(blocks),
    }


def test_the_formatting_of_the_ribbon_is_part_of_the_format() -> None:
    styled = doc(
        paragraph(
            text("barré", {"type": "strike"}),
            text("surligné", {"type": "highlight", "attrs": {"color": "#fff59d"}}),
            text("stylé", {"type": "text_style", "attrs": {"font": "georgia", "size": 14}}),
            text(" [1]", {"type": "source_ref", "attrs": {"source": "S1"}}),
        ),
        {"type": "heading", "attrs": {"id": "b2", "level": 2}, "content": [text("Titre")]},
        {
            "type": "bullet_list",
            "attrs": {"id": "b3"},
            "content": [{"type": "list_item", "content": [paragraph(text("un"))]}],
        },
        {"type": "citation", "attrs": {"id": "b4", "source": "S1"}, "content": [paragraph()]},
        {"type": "separateur", "attrs": {"id": "b5"}},
    )
    assert check(styled, {"S1"}) == []


def test_a_document_outside_the_format_is_refused_with_its_reasons() -> None:
    def errors(*marks: dict[str, Any]) -> list[str]:
        return check(doc(paragraph(text("x", *marks))), {"S1"})

    assert errors({"type": "link", "attrs": {"href": "javascript:alert(1)"}}) == [
        "content[0].content[0]: a link goes to http, https or mailto"
    ]
    assert errors({"type": "source_ref", "attrs": {"source": "S9"}}) == [
        "content[0].content[0]: a reference cites a source of the article"
    ]
    assert errors({"type": "highlight", "attrs": {"color": "#123456"}})
    assert errors({"type": "text_style", "attrs": {"font": "Comic Sans"}})
    assert errors({"type": "text_style", "attrs": {"size": 13}})
    assert errors({"type": "text_style", "attrs": {"size": 12.0}})  # 12.0pt would not match
    assert errors({"type": "text_style", "attrs": {"color": "red", "style": "x"}})
    assert errors({"type": "underline"}) == [
        "content[0].content[0].marks: unknown or repeated mark"
    ]
    assert check(doc({"type": "script", "attrs": {}}), set()) == ["content[0]: unknown block"]
    assert check({"type": "doc", "attrs": {"version_schema": 1}, "content": []}, set())
    assert check("<p>html</p>", set()) == ["document: a doc is required"]
    assert check(doc(paragraph(text("x" * 1_100_000))), set()) == ["document: too large"]


def test_a_block_keeps_its_origin_until_it_changes() -> None:
    previous = doc(paragraph(text("Un"), id="b1"), paragraph(text("Deux"), id="b2"))
    edited = doc(
        paragraph(text("Un"), id="b1", origine="humain"),  # the origin sent is not trusted
        paragraph(text("Deux, retouché"), id="b2"),
        paragraph(text("Suite de deux"), id="b2"),  # split: the editor copies the id
        paragraph(text("Trois"), id=None),
    )
    saved = with_origins(edited, previous, SOURCES)
    blocks = saved["content"]
    assert [b["attrs"]["origine"] for b in blocks] == ["ia", "ia_modifie", "ia_modifie", "humain"]
    assert [b["attrs"]["id"] for b in blocks] == ["b1", "b2", "b3", "b4"]
    assert saved["attrs"]["sources"] == SOURCES


def test_the_render_is_controlled_and_publication_leaves_the_presentation_out() -> None:
    styled = doc(
        paragraph(
            text(
                "<b>",
                {"type": "bold"},
                {"type": "text_style", "attrs": {"size": 14, "color": "#c00000"}},
                {"type": "strike"},
            ),
            text("vu", {"type": "highlight", "attrs": {"color": "#fff59d"}}),
        )
    )
    assert render(styled, extras=False) == (
        '<p><span style="font-size: 14pt; color: #c00000"><s><strong>&lt;b&gt;</strong></s>'
        '</span><mark style="background-color: #fff59d">vu</mark></p>'
    )
    assert render(styled, extras=False, publication=True) == (
        '<p><s><strong>&lt;b&gt;</strong></s><mark style="background-color: #fff59d">vu</mark></p>'
    )
