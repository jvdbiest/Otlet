#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check that every shipped dependency has a licence compatible with the AGPL-3.0 (B07).

Usage:
    <runtime venv>/python tools/check_licenses.py python
    python tools/check_licenses.py npm <package-lock.json>

Standard library only. The filter is the one of TECH_CHOICES.md §1.1: permissive licences,
MPL, LGPL, GPL-3.0, AGPL-3.0 and the PostgreSQL licence pass; source-available (SSPL, BSL,
Elastic…), proprietary and GPL-2.0-only licences fail, and so does any licence the script
cannot identify. Only what is shipped is checked: in "python" mode, every distribution
installed in the interpreter that runs the script, which must be an environment synced
without the dev group (`uv sync --no-dev`); in "npm" mode, packages that are not dev-only.
Exits 1 and lists the offending packages otherwise.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from pathlib import Path

ALLOWED = {
    "0BSD", "AFL-2.1", "Apache-2.0", "BlueOak-1.0.0", "BSD-2-Clause", "BSD-3-Clause",
    "CC0-1.0", "CC-BY-4.0", "HPND", "ISC", "MIT", "MIT-0", "MIT-CMU", "MPL-2.0", "PostgreSQL",
    "PSF-2.0", "Python-2.0", "Unlicense", "Zlib",
    "LGPL-2.0-or-later", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later",
}  # fmt: skip

# Free-text licence fields and trove classifiers seen in practice, mapped to SPDX.
ALIASES = {
    "mit": "MIT",
    "mit license": "MIT",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd 2-clause license": "BSD-2-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "3-clause bsd license": "BSD-3-Clause",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "python software foundation license": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    "isc license (iscl)": "ISC",
    "the unlicense (unlicense)": "Unlicense",
    "gnu lesser general public license v2 or later (lgplv2+)": "LGPL-2.0-or-later",
    "gnu lesser general public license v3 (lgplv3)": "LGPL-3.0-only",
    "gnu lesser general public license v3 or later (lgplv3+)": "LGPL-3.0-or-later",
}

TOKEN = re.compile(r"\(|\)|[^\s()]+")


def allowed_expression(expression: str) -> bool:
    """Evaluate an SPDX expression: OR needs one allowed side, AND needs both, WITH keeps the
    licence on its left (exceptions only add permissions)."""
    tokens = TOKEN.findall(expression)
    position = 0

    def parse_or() -> bool:
        nonlocal position
        result = parse_and()
        while position < len(tokens) and tokens[position].upper() == "OR":
            position += 1
            right = parse_and()
            result = result or right
        return result

    def parse_and() -> bool:
        nonlocal position
        result = parse_atom()
        while position < len(tokens) and tokens[position].upper() == "AND":
            position += 1
            right = parse_atom()
            result = result and right
        return result

    def parse_atom() -> bool:
        nonlocal position
        if position >= len(tokens):
            raise ValueError(f"incomplete licence expression: {expression!r}")
        item = tokens[position]
        position += 1
        if item == "(":
            result = parse_or()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError(f"unbalanced licence expression: {expression!r}")
            position += 1
        else:
            result = item.removesuffix("+") in ALLOWED or item in ALLOWED
        if position < len(tokens) and tokens[position].upper() == "WITH":
            position += 2
        return result

    try:
        result = parse_or()
    except ValueError:
        return False
    # Anything left over is not an SPDX expression ("SEE LICENSE IN …"): not identified.
    return result and position == len(tokens)


def python_licence(name: str) -> str | None:
    """SPDX expression of an installed distribution, from its metadata."""
    metadata = importlib.metadata.metadata(name)
    if expression := metadata.get("License-Expression"):
        return str(expression)
    classifiers = [
        c.split("::")[-1].strip().lower()
        for c in metadata.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    known = [ALIASES[c] for c in classifiers if c in ALIASES]
    if known:
        return " OR ".join(known)
    text = (metadata.get("License") or "").strip()
    # Some packages write a bare SPDX identifier, or an SPDX expression, in the free-text field
    # (lxml: BSD-3-Clause; tqdm: MPL-2.0 AND MIT).
    if text in ALLOWED or (text and allowed_expression(text)):
        return text
    return ALIASES.get(text.lower())


def check_python() -> list[str]:
    failures = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        licence = python_licence(name)
        if licence is None:
            failures.append(f"{name}: licence non identifiée")
        elif not allowed_expression(licence):
            failures.append(f"{name}: {licence}")
    return sorted(failures)


def check_npm(lock: Path) -> list[str]:
    packages = json.loads(lock.read_text(encoding="utf-8"))["packages"]
    failures = []
    for path, package in packages.items():
        if not path or package.get("dev", False):
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        licence = package.get("license")
        if not licence:
            failures.append(f"{name}: licence non identifiée")
        elif not allowed_expression(licence):
            failures.append(f"{name}: {licence}")
    return failures


def main(argv: list[str]) -> int:
    if argv == ["python"]:
        failures = check_python()
    elif len(argv) == 2 and argv[0] == "npm":
        failures = check_npm(Path(argv[1]))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    if failures:
        print("Dépendances dont la licence n'est pas compatible avec l'AGPL-3.0 (ou inconnue) :")
        for line in failures:
            print(f"  {line}")
        print("Voir TECH_CHOICES.md §1.1 ; une exception exige un ADR.")
        return 1
    print(f"Licences ({argv[0]}) : toutes compatibles avec l'AGPL-3.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
