#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Check that every commit in a range carries a DCO sign-off (ADR-0013).

Usage: python tools/check_dco.py <base>..<head>

Standard library only. A commit passes when one of its "Signed-off-by"
trailers names its author's e-mail address (case-insensitive). Merge
commits are skipped. Exits 1 and lists the offending commits otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys

FIELD = "\x1f"
RECORD = "\x1e"
LOG_FORMAT = FIELD.join(["%H", "%an", "%ae", "%s", "%(trailers:key=Signed-off-by,valueonly)"])
EMAIL = re.compile(r"<([^<>]+)>\s*$")


def unsigned_commits(revision_range: str) -> list[str]:
    log = subprocess.run(  # noqa: S603
        ["git", "log", "--no-merges", f"--format={LOG_FORMAT}{RECORD}", revision_range],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    failures = []
    for record in log.split(RECORD):
        if not record.strip():
            continue
        sha, name, email, subject, trailers = record.strip("\n").split(FIELD)
        signers = {
            match.group(1).strip().lower()
            for line in trailers.splitlines()
            if (match := EMAIL.search(line))
        }
        if email.strip().lower() not in signers:
            failures.append(f"{sha[:12]} {subject} ({name} <{email}>)")
    return failures


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    failures = unsigned_commits(argv[0])
    if failures:
        print("Commits sans « Signed-off-by » correspondant à l'auteur :")
        for line in failures:
            print(f"  {line}")
        print("Signez-les avec « git commit -s » (voir CONTRIBUTING.md).")
        return 1
    print("Signature DCO : tous les commits sont signés.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
