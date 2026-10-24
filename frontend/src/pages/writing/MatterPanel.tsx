// SPDX-License-Identifier: AGPL-3.0-or-later
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { matterQuery, type BriefLength, type BriefMode, type BriefNature, type MatterView } from "../../writing.ts";
import { styles } from "../watch/styles.ts";

type Criterion = MatterView["criteria"][number];

const MARKS = { ok: "✓", warn: "!", fail: "✗" } as const;
const INTRO_KEY = "otlet.matter.intro";

function seenIntro(): boolean {
  try {
    return window.localStorage.getItem(INTRO_KEY) !== null;
  } catch {
    return true;
  }
}

function rememberIntro(): void {
  try {
    window.localStorage.setItem(INTRO_KEY, "1");
  } catch {
    // Without storage, the line comes back next time: no harm.
  }
}

/** The matter of a brief (ADR-0041): its level and the half-sentence that explains it, then the
 * five criteria with their value and what to do. The rule is the server's; this only shows it.
 * Open when the matter is limited or insufficient, one line when it is enough. `compact`: the
 * level alone, read-only, next to « Générer ». It never blocks saving a brief. */
export function MatterPanel({
  workspaceId,
  itemIds,
  length,
  mode,
  nature,
  compact = false,
}: {
  workspaceId: string;
  itemIds: string[];
  length: BriefLength;
  mode: BriefMode;
  nature: BriefNature;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const matter = useQuery({
    ...matterQuery(workspaceId, { item_ids: itemIds, length, mode, nature }),
    enabled: itemIds.length > 0,
    placeholderData: keepPreviousData,
  });
  const [intro, setIntro] = useState(() => !seenIntro());
  if (itemIds.length === 0 || matter.data === undefined) {
    return null;
  }
  const { level, reason, criteria } = matter.data;
  const why = reason === null ? null : reasonText(t, level, criteria.find((c) => c.name === reason));
  const title = (
    <>
      <strong>{t(`matter.levels.${level}`)}</strong>
      {why !== null && ` : ${why}`}
    </>
  );
  const tone = level === "insufficient" ? styles.warning : level === "limited" ? styles.notice : styles.meta;
  if (compact) {
    return <p className={tone}>{title}</p>;
  }
  return (
    <div className={tone} aria-live="polite">
      <details key={level} open={level !== "enough"}>
        <summary>{title}</summary>
        {intro && (
          <p className={styles.help}>
            {t("matter.intro")}{" "}
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                rememberIntro();
                setIntro(false);
              }}
            >
              {t("matter.understood")}
            </button>
          </p>
        )}
        <ul className={styles.criteria}>
          {criteria.map((criterion) => (
            <li key={criterion.name}>
              <span aria-hidden="true" className={styles.mark}>
                {criterion.mark === null ? "–" : criterion.informative ? "i" : MARKS[criterion.mark]}
              </span>{" "}
              <strong>{t(`matter.criteria.${criterion.name}`)}</strong> : {valueText(t, criterion)}
              {!criterion.informative && criterion.mark !== null && criterion.mark !== "ok" && (
                <Action criterion={criterion} />
              )}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

type T = TFunction;

function reasonText(t: T, level: MatterView["level"], criterion: Criterion | undefined): string | null {
  if (criterion === undefined) {
    return null;
  }
  if (criterion.name === "freshness") {
    if (criterion.mark === "fail") {
      return t("matter.reasons.freshnessOld");
    }
    return t("matter.reasons.freshness");
  }
  if (criterion.name === "corroboration") {
    return null;
  }
  const count = criterion.value ?? 0;
  return level === "insufficient"
    ? t(`matter.reasons.fail.${criterion.name}`, { count })
    : t(`matter.reasons.warn.${criterion.name}`, { count });
}

function valueText(t: T, criterion: Criterion): string {
  const count = criterion.value ?? 0;
  switch (criterion.name) {
    case "sources":
      return t("matter.values.sources", { count });
    case "publishers":
      return t("matter.values.publishers", { count });
    case "words":
      return criterion.mark === "warn" && criterion.longest !== null
        ? t("matter.values.wordsUpTo", { count, length: t(`matter.lengths.${criterion.longest}`) })
        : t("matter.values.words", { count });
    case "freshness":
      return t("matter.values.freshness", { count });
    case "corroboration":
      return t("matter.values.corroboration");
  }
}

/** What to do about a criterion in default: a link where Otlet has the place for it. */
function Action({ criterion }: { criterion: Criterion }) {
  const { t } = useTranslation();
  const action = t(`matter.actions.${criterion.name}`);
  if (criterion.name === "words") {
    return <span className={styles.help}> {t(criterion.mark === "fail" ? "matter.actions.wordsFail" : "matter.actions.words")}</span>;
  }
  return (
    <>
      {" "}
      <Link to="/veille" className={styles.meta}>
        {action}
      </Link>
    </>
  );
}
