# SPDX-License-Identifier: AGPL-3.0-or-later
"""TRI1: the hand-written reference, by rank in the frozen sets (items.jsonl), written before any
measure: docs/spikes/TRI1.md §3. Standard library only.

    python3 make_labels.py <items.jsonl> > labels.csv

R: answers the question or is mainly about it. T: same theme, does not answer. H: off the subject.
"""

import csv
import json
import sys


def ranks(text: str) -> set[int]:
    out: set[int] = set()
    for part in text.split():
        first, _, last = part.partition("-")
        out |= set(range(int(first), int(last or first) + 1))
    return out


LABELS = {
    "Pourquoi risque": ("2 3 11 17 25 35", "7 9 13 20 22 24 26 29 30 32 36 37 38"),
    "La situation": ("1 3 5", "9 11"),
    "Que rachète": ("0 1", "2 3 4 6"),
    "Quelles sont": (
        "0-24 29-32 34-42 44-58 61-65 71 99",
        "25-28 33 43 59 60 66-70 72 86 88-91 93 94 96-98 104 105 107",
    ),
    "Les pertes": ("1 6 8 10 11 13 28 36 39", "0 2 4 9 12 14 15 17 18 24 43 45"),
    "Les essais": (
        "2 4 13 20 22 25 46 53 54 61 63",
        "0 5-10 19 28 29 34 44 50 60 62 64",
    ),
    "Les prix": (
        "2 3 5 7 8 9 11 13 24",
        "0 1 12 17-20 22 23 25-29 31 32",
    ),
}


def main() -> None:
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["question", "rank", "id", "label", "summary", "title"])
    for line in open(sys.argv[1], encoding="utf-8"):
        item = json.loads(line)
        key = next((k for k in LABELS if item["question"].startswith(k)), None)
        if key is None:
            continue
        answers, theme = LABELS[key]
        rank = item["rank"]
        label = "R" if rank in ranks(answers) else "T" if rank in ranks(theme) else "H"
        has = "oui" if item["summary"].strip() else "non"
        out.writerow([key, rank, item["id"], label, has, item["title"]])


if __name__ == "__main__":
    main()
