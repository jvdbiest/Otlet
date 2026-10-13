# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3: converts and renders the whole corpus with the Python pipeline, validates every
document against the schema, and compares the extracted elements with expected.json.
Pipeline check before any CMS (not a criterion of the spike). Exit 1 on any difference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from otlet_doc import extract, markdown, paste, render  # noqa: E402

KEYS = ("headings", "links", "citations", "sources", "mention_ia")


def load(name: str) -> dict:
    path = HERE / "corpus" / name
    if name.startswith("written"):
        return json.loads(path.read_text(encoding="utf-8"))
    if name.startswith("ai"):
        return markdown.convert(path.read_text(encoding="utf-8"))
    sources = json.loads(path.with_name(path.name.replace(".html", ".sources.json")).read_text(encoding="utf-8"))
    return paste.convert(path.read_text(encoding="utf-8"), sources)


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    schema = json.loads((HERE / "schema" / "document-v1.schema.json").read_text(encoding="utf-8"))
    expected = json.loads((HERE / "corpus" / "expected.json").read_text(encoding="utf-8"))
    failures = 0
    for name, wanted in expected.items():
        document = load(name)
        if jsonschema is not None:
            errors = list(jsonschema.Draft202012Validator(schema).iter_errors(document))
            if errors:
                failures += 1
                print(f"{name}: schema: {errors[0].message[:160]}")
                continue
        got = extract.extract(render.render(document))
        diffs = [key for key in KEYS if got[key] != wanted[key]]
        if diffs:
            failures += 1
            print(f"{name}: {diffs}")
            for key in diffs[:2]:
                print("  expected", wanted[key])
                print("  got     ", got[key])
    print(f"{len(expected) - failures}/{len(expected)} documents conform"
          + ("" if jsonschema else " (schema not checked: jsonschema missing)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
