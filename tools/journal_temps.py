#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Review of the time log (docs/projet/journal-temps.md).

Usage: python tools/journal_temps.py [--log PATH] [--backlog PATH] [--etape E0]

Standard library only. The log holds one rough line per finished task
(no per-session entries), so weekly criteria CA2 and CA3 are left to the
maintainer's judgement. Prints, per task, actual hours against the
estimate, the step total against CA1 thresholds, and the measured velocity.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = {"preuve", "fonction", "compte", "entretien", "projet"}
FEATURE_DOMAINS = {"preuve", "fonction", "compte"}
# Central estimate of each roadmap step, in feature hours (ROADMAP.md, annex B).
CENTRAL_ESTIMATE = {"E0": 220, "E1": 640, "E2": 612.5}


def read_csv(path: Path) -> csv.DictReader[str]:
    """Read a CSV saved as UTF-8 (with or without BOM) or, by Windows editors, as cp1252."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    return csv.DictReader(io.StringIO(text, newline=""))


def read_log(path: Path) -> list[dict[str, object]]:
    entries = []
    for n, row in enumerate(read_csv(path), start=2):
        try:
            day = dt.date.fromisoformat(row["date"].strip())
            hours = float(row["heures"].replace(",", "."))
        except (KeyError, ValueError) as exc:
            sys.exit(f"{path}:{n}: ligne invalide ({exc})")
        domain = row["domaine"].strip()
        if domain not in DOMAINS:
            sys.exit(f"{path}:{n}: domaine inconnu « {domain} »")
        task = (row.get("tache") or "-").strip()
        if domain in {"preuve", "fonction"} and task in {"", "-"}:
            sys.exit(f"{path}:{n}: tâche obligatoire pour le domaine « {domain} »")
        entries.append(
            {
                "date": day,
                "heures": hours,
                "domaine": domain,
                "etape": row["etape"].strip(),
                "tache": task,
            }
        )
    return entries


def report_tasks(entries: list[dict[str, object]], backlog: Path, step: str) -> None:
    spent: dict[str, float] = defaultdict(float)
    for e in entries:
        if e["etape"] == step and e["domaine"] in FEATURE_DOMAINS:
            spent[e["tache"]] += e["heures"]  # type: ignore[index,operator]
    cumulated = sum(spent.values())
    central = CENTRAL_ESTIMATE.get(step)
    print(f"\nÉtape {step} : {cumulated:.2f} h de fonctions cumulées")
    if central:
        print(f"  CA1 : alerte à {central * 1.25:.0f} h, réduction à {central * 1.5:.0f} h")
        if cumulated > central * 1.5:
            print("  ALERTE CA1 (+50 %) : appliquer la réduction préparée suivante")
        elif cumulated > central * 1.25:
            print("  ALERTE CA1 (+25 %) : ré-estimer le reste de l'étape")
    if not backlog.exists():
        return
    tasks = list(read_csv(backlog))
    done_est = done_real = 0.0
    print("  Tâches commencées (réel / estimé)")
    for t in tasks:
        est, real = float(t["estimation_h"]), spent.get(t["id"], 0.0)
        if real or t["statut"] != "a_faire":
            flag = "  ⚠" if real > est * 1.10 else ""
            print(f"    {t['id']:<5} {t['statut']:<8} {real:5.2f} / {est:4.1f} h{flag}")
        if t["statut"] == "fait" and real:
            done_est += est
            done_real += real
    no_hours = [t["id"] for t in tasks if t["statut"] == "fait" and t["id"] not in spent]
    if no_hours:
        print(f"  Tâches faites sans heures au journal : {', '.join(no_hours)}")
    unknown = sorted(set(spent) - {t["id"] for t in tasks} - {"-"})
    if unknown:
        print(f"  Tâches absentes du backlog : {', '.join(unknown)}")
    if done_real:
        print(f"  Vélocité (estimé ÷ réel, tâches faites) : {done_est / done_real:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=ROOT / "docs/projet/journal-temps.csv")
    parser.add_argument("--backlog", type=Path, default=ROOT / "docs/projet/backlog-E0.csv")
    parser.add_argument("--etape", default="E0")
    args = parser.parse_args()
    entries = read_log(args.log)
    if not entries:
        print("Journal vide.")
        return
    report_tasks(entries, args.backlog, args.etape)


if __name__ == "__main__":
    main()
