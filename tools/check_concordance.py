# SPDX-License-Identifier: AGPL-3.0-or-later
"""Concordance test (ADR-0023 §4), Python side: the HTML the editor's extensions gave for each
document of tools/concordance (frontend/tools/concordance.ts) must be the Python renderer's,
after the normalization of the S3 report (tree reparsed, attributes sorted, whitespace folded,
data-* attributes removed, entities decoded), and inline styles written one way; the closed
lists of the format must be the same.

    python3 tools/check_concordance.py <folder written by concordance.ts>
"""

from __future__ import annotations

import json
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))

from otlet.writing.domain import document  # noqa: E402  (the renderer, standard library only)

SPACE = " \t\n\r\f"


class _Canonical(HTMLParser):
    VOID = {"br", "img", "hr", "meta", "link", "input", "source", "col", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept = sorted(
            (k, _style(v or "") if k == "style" else v or "")
            for k, v in attrs
            if not k.startswith("data-")
        )
        self.out.append(f"<{tag}{''.join(f' {k}="{escape(v)}"' for k, v in kept)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        folded = " ".join(data.split())
        if folded:
            lead = " " if data[:1] in SPACE else ""
            trail = " " if data[-1:] in SPACE else ""
            self.out.append(escape(lead + folded + trail, quote=False))


def _style(value: str) -> str:
    """An inline style as a DOM writes it back or not: « a: b; c: d » and « a:b;c:d; » alike,
    one kind of quotes."""
    declarations = (" ".join(d.replace("'", '"').split()) for d in value.split(";"))
    pairs = (d.replace(" :", ":").replace(":", ": ", 1).replace(":  ", ": ") for d in declarations)
    return "; ".join(pair for pair in pairs if pair)


def canonical(html: str) -> str:
    parser = _Canonical()
    parser.feed(html)
    parser.close()
    return "".join(parser.out)


def main(folder: Path) -> int:
    failures = []
    names = sorted((ROOT / "tools" / "concordance").glob("*.json"))
    for path in names:
        doc = json.loads(path.read_text(encoding="utf-8"))
        python = canonical(document.render(doc, extras=False))
        editor = canonical((folder / f"{path.stem}.html").read_text(encoding="utf-8"))
        if python != editor:
            at = next(
                (i for i, (a, b) in enumerate(zip(python, editor, strict=False)) if a != b),
                min(len(python), len(editor)),
            )
            failures.append(
                f"{path.name}: differs at {at}\n  python: …{python[max(at - 60, 0) : at + 80]}\n"
                f"  editor: …{editor[max(at - 60, 0) : at + 80]}"
            )
    lists = json.loads((folder / "lists.json").read_text(encoding="utf-8"))
    expected = {
        "fonts": document.FONTS,
        "sizes": list(document.SIZES),
        "colors": list(document.COLORS),
        "highlights": list(document.HIGHLIGHTS),
    }
    for key, value in expected.items():
        if lists[key] != value:
            failures.append(f"closed list « {key} » differs: editor {lists[key]!r}")
    for failure in failures:
        print(failure)
    print(f"concordance: {len(names) - len(failures)} / {len(names)} documents identical")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
