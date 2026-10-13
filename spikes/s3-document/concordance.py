# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3, criterion C3: Python rendering vs editor rendering, after the normalization fixed in
docs/spikes/S3.md §3.3 (tree reparsed, attributes sorted, whitespace folded, data-* attributes
removed, entities decoded). Also checks the JSON of the 10 pastes through Tiptap's parser
against the schema. Writes results/concordance-<time>.json."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).parent
BUILD = HERE / "build"
SPACE = " \t\n\r\f"


class _Canonical(HTMLParser):
    VOID = {"br", "img", "hr", "meta", "link", "input", "source", "col", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept = sorted((k, v or "") for k, v in attrs if not k.startswith("data-"))
        rendered = "".join(f' {k}="{escape(v)}"' for k, v in kept)
        self.out.append(f"<{tag}{rendered}>")

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


def canonical(html: str) -> str:
    parser = _Canonical()
    parser.feed(html)
    parser.close()
    return "".join(parser.out)


def compare(editor: str) -> dict[str, object]:
    names = sorted(p.name for p in (BUILD / "html-python").glob("*.html"))
    differing = []
    for name in names:
        python = canonical((BUILD / "html-python" / name).read_text(encoding="utf-8"))
        other = canonical((BUILD / f"html-{editor}" / name).read_text(encoding="utf-8"))
        if python != other:
            position = next((i for i, (a, b) in enumerate(zip(python, other)) if a != b), min(len(python), len(other)))
            differing.append({"document": name, "python": python[max(0, position - 60) : position + 80], editor: other[max(0, position - 60) : position + 80]})
    return {"documents": len(names), "concordant": len(names) - len(differing), "rate": round((len(names) - len(differing)) / len(names), 3), "differences": differing}


def pastes_valid() -> dict[str, object]:
    import jsonschema

    schema = json.loads((HERE / "schema" / "document-v1.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    results = {}
    for path in sorted((BUILD / "paste-tiptap").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        errors = [e.message[:160] for e in validator.iter_errors(document)]
        kinds = sorted({block["type"] for block in document["content"]})
        results[path.name] = {"valid": not errors, "errors": errors[:3], "block_types": kinds}
    return results


def main() -> int:
    result = {
        "criterion": "C3",
        "normalization": "reparse, sorted attributes, folded whitespace, data-* removed, entities decoded",
        "tiptap": compare("tiptap"),
        "blocknote": compare("blocknote"),
        "tiptap_paste_schema": pastes_valid(),
    }
    (HERE / "results").mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = HERE / "results" / f"concordance-{stamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: (v["rate"] if isinstance(v, dict) and "rate" in v else None) for k, v in result.items() if k in ("tiptap", "blocknote")}))
    print(f"Result: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
