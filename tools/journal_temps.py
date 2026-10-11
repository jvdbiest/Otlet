#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Weekly review of the time log (docs/projet/journal-temps.md).

Usage: python tools/journal_temps.py [--log PATH] [--backlog PATH] [--etape E0]

Standard library only. Prints weekly gross hours, stop-criteria alerts
(CA1, CA2, CA3, CA5, CA6), monthly share per domain and, per task,
actual hours against the estimate, plus the measured velocity.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = {"preuve", "fonction", "compte", "entretien", "projet", "absence"}
FEATURE_DOMAINS = {"preuve", "fonction", "compte"}
# Central estimate of each roadmap step, in feature hours (ROADMAP.md, annex B).
CENTRAL_ESTIMATE = {"E0": 220, "E1": 640, "E2": 612.5}


def read_log(path: Path) -> list[dict[str, object]]:
    entries = []
    with path.open(newline="", encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
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
                {"date": day, "heures": hours, "domaine": domain,
                 "etape": row["etape"].strip(), "tache": task}
            )
    return entries


def monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def weekly(entries: list[dict[str, object]]) -> list[tuple[dt.date, float, bool]]:
    """Every week from the first entry to the current one: (monday, hours, off)."""
    hours: dict[dt.date, float] = defaultdict(float)
    off: set[dt.date] = set()
    for e in entries:
        week = monday(e["date"])  # type: ignore[arg-type]
        hours[week] += e["heures"]  # type: ignore[operator]
        if e["domaine"] == "absence":
            off.add(week)
    if not hours:
        return []
    week, last = min(hours), monday(dt.date.today())
    out = []
    while week <= last:
        out.append((week, hours.get(week, 0.0), week in off))
        week += dt.timedelta(weeks=1)
    return out


def report_weeks(weeks: list[tuple[dt.date, float, bool]]) -> None:
    print("Heures brutes par semaine (8 dernières)")
    for week, h, off in weeks[-8:]:
        print(f"  {week.isocalendar().year}-S{week.isocalendar().week:02d}  {h:5.2f} h"
              + ("  (absence)" if off else ""))
    missing = [w for w, h, off in weeks if h == 0 and not off]
    if missing:
        print(f"  Semaines sans aucune ligne : {len(missing)} (saisir 0 h en « absence » si non travaillées)")

    worked = [h for _, h, off in weeks if not off]
    if len(worked) >= 8 and sum(worked[-8:]) / 8 < 12:
        print("  ALERTE CA2 : moyenne < 12 h sur 8 semaines → calendrier décalé, pas de rattrapage")
    if len(worked) >= 12 and sum(worked[-12:]) / 12 < 8:
        print("  ALERTE CA2 : moyenne < 8 h sur 12 semaines → mode pause")
    streak = 0
    for _, h, off in weeks:
        streak = streak + 1 if (h > 20 and not off) else 0
    if streak >= 4:
        print(f"  ALERTE CA3 : > 20 h depuis {streak} semaines → retour obligatoire sous le plafond")


def report_month(entries: list[dict[str, object]]) -> None:
    today = dt.date.today()
    start = today.replace(day=1)
    month = [e for e in entries if e["date"] >= start]  # type: ignore[operator]
    total = sum(e["heures"] for e in month)  # type: ignore[misc]
    print(f"\nRépartition du mois en cours ({total:.2f} h)")
    if not total:
        return
    by_domain: dict[str, float] = defaultdict(float)
    for e in month:
        by_domain[e["domaine"]] += e["heures"]  # type: ignore[index,operator]
    for domain in sorted(by_domain):
        print(f"  {domain:<10} {by_domain[domain]:6.2f} h  {by_domain[domain] / total:5.1%}")
    features = sum(by_domain[d] for d in FEATURE_DOMAINS)
    if features and by_domain["compte"] / features > 0.15:
        print("  ALERTE CA5 : parcours de compte > 15 % des heures de fonctions")
    if by_domain["entretien"] / total > 0.20:
        print("  Signal CA6 : entretien > 20 % ce mois (le critère porte sur un trimestre)")


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
    with backlog.open(newline="", encoding="utf-8") as f:
        tasks = list(csv.DictReader(f))
    done_est = done_real = 0.0
    print("  Tâches commencées (réel / estimé)")
    for t in tasks:
        est, real = float(t["estimation_h"]), spent.get(t["id"], 0.0)
        if real or t["statut"] != "a_faire":
            flag = "  ⚠" if real > est * 1.10 else ""
            print(f"    {t['id']:<5} {t['statut']:<8} {real:5.2f} / {est:4.1f} h{flag}")
        if t["statut"] == "fait":
            done_est += est
            done_real += real
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
    report_weeks(weekly(entries))
    report_month(entries)
    report_tasks(entries, args.backlog, args.etape)


if __name__ == "__main__":
    main()
