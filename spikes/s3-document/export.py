# SPDX-License-Identifier: AGPL-3.0-or-later
"""S3: writes build/json/<doc>.json (the corpus in the format) and build/html-python/<doc>.html
(the Python rendering of the body, without mention and Sources) for the editors to compare."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from otlet_doc import render  # noqa: E402
from selfcheck import load  # noqa: E402


def key(name: str) -> str:
    return name.replace("/", "__").rsplit(".", 1)[0]


def main() -> None:
    expected = json.loads((HERE / "corpus" / "expected.json").read_text(encoding="utf-8"))
    for folder in ("json", "html-python"):
        (HERE / "build" / folder).mkdir(parents=True, exist_ok=True)
    for name in expected:
        document = load(name)
        (HERE / "build" / "json" / f"{key(name)}.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
        (HERE / "build" / "html-python" / f"{key(name)}.html").write_text(
            render.render(document, extras=False), encoding="utf-8"
        )
    print(f"{len(expected)} documents exported")


if __name__ == "__main__":
    main()
