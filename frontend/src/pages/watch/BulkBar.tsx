// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { type BulkAction, useBulkTriage } from "../../triage.ts";
import { styles } from "./styles.ts";

const ACTIONS: readonly BulkAction[] = ["keep", "pin", "archive", "dismiss", "to_sort"];
const BRIEF_MAX = 20; // the items of one brief

/** Selection of the items, and the actions that apply to all of them at once (I1). « Tout
 * sélectionner » takes every item of the filters, over all pages, when `everything` gives them
 * (Joël, 2026-10-20); otherwise the items shown (a search). */
export function BulkBar({
  workspaceId,
  visible,
  selected,
  onSelect,
  everything,
}: {
  workspaceId: string;
  visible: string[];
  selected: string[];
  onSelect: (ids: string[]) => void;
  everything?: (() => Promise<string[]>) | undefined;
}) {
  const { t } = useTranslation();
  const triage = useBulkTriage(workspaceId);
  const [done, setDone] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [gathering, setGathering] = useState(false);
  const [failed, setFailed] = useState(false);
  const all = useRef<HTMLInputElement>(null);
  // Without `everything`, the selection is that of the items shown.
  const chosen = everything === undefined ? selected.filter((id) => visible.includes(id)) : selected;
  const allSelected =
    everything === undefined
      ? visible.length > 0 && chosen.length === visible.length
      : total !== null && chosen.length >= total && total > 0;
  useEffect(() => {
    if (all.current !== null) {
      all.current.indeterminate = chosen.length > 0 && !allSelected;
    }
  }, [chosen.length, allSelected]);
  if (visible.length === 0) {
    // An action may empty the list: its result stays readable.
    return done === null ? null : (
      <p className={styles.meta} role="status">
        {done}
      </p>
    );
  }
  const busy = triage.isPending || gathering;
  const finish = (message: string) => {
    setDone(message);
    setTotal(null);
    onSelect([]);
  };
  return (
    <div className={styles.bulkBar} role="region" aria-label={t("triage.bulk.label")}>
      <label className={styles.check}>
        <input
          ref={all}
          type="checkbox"
          checked={allSelected}
          disabled={gathering}
          onChange={(event) => {
            setDone(null);
            setFailed(false);
            if (!event.target.checked) {
              setTotal(null);
              onSelect([]);
            } else if (everything === undefined) {
              onSelect(visible);
            } else {
              setGathering(true);
              everything()
                .then((ids) => {
                  setTotal(ids.length);
                  onSelect(ids);
                })
                .catch(() => {
                  setFailed(true);
                })
                .finally(() => {
                  setGathering(false);
                });
            }
          }}
        />{" "}
        {t("triage.bulk.all")}
      </label>
      <span className={styles.meta} aria-live="polite">
        {gathering
          ? t("triage.bulk.gathering")
          : chosen.length > 0
            ? t("triage.bulk.selected", { count: chosen.length })
            : done}
      </span>
      {chosen.length > 0 && (
        <div className={styles.row}>
          {chosen.length <= BRIEF_MAX ? (
            <Link to="/redaction/nouveau" search={{ items: chosen.join(",") }} className={styles.primary}>
              {t("triage.bulk.brief")}
            </Link>
          ) : (
            <span className={styles.meta}>{t("triage.bulk.briefMax", { max: BRIEF_MAX })}</span>
          )}
          {ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => {
                triage.mutate(
                  { itemIds: chosen, action },
                  {
                    onSuccess: (count) => {
                      finish(t(`triage.bulk.done.${action}`, { count }));
                    },
                  },
                );
              }}
            >
              {t(`triage.bulk.${action}`)}
            </button>
          ))}
        </div>
      )}
      {(triage.error !== null || failed) && (
        <span role="alert" className={styles.error}>
          {t("errors.generic")}
        </span>
      )}
    </div>
  );
}
