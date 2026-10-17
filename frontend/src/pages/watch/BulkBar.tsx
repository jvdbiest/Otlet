// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { type BulkAction, useBulkTriage } from "../../triage.ts";
import { styles } from "./styles.ts";

const ACTIONS: readonly BulkAction[] = ["keep", "pin", "archive", "dismiss", "to_sort"];

/** Selection of the shown items, and the actions that apply to all of them at once (I1). */
export function BulkBar({
  workspaceId,
  visible,
  selected,
  onSelect,
}: {
  workspaceId: string;
  visible: string[];
  selected: string[];
  onSelect: (ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const triage = useBulkTriage(workspaceId);
  const [done, setDone] = useState<string | null>(null);
  const all = useRef<HTMLInputElement>(null);
  const shown = selected.filter((id) => visible.includes(id));
  const allSelected = visible.length > 0 && shown.length === visible.length;
  useEffect(() => {
    if (all.current !== null) {
      all.current.indeterminate = shown.length > 0 && !allSelected;
    }
  }, [shown.length, allSelected]);
  if (visible.length === 0) {
    // An action may empty the list: its result stays readable.
    return done === null ? null : (
      <p className={styles.meta} role="status">
        {done}
      </p>
    );
  }
  const busy = triage.isPending;
  const finish = (message: string) => {
    setDone(message);
    onSelect([]);
  };
  return (
    <div className={styles.bulkBar} role="region" aria-label={t("triage.bulk.label")}>
      <label className={styles.check}>
        <input
          ref={all}
          type="checkbox"
          checked={allSelected}
          onChange={(event) => {
            onSelect(event.target.checked ? visible : []);
            setDone(null);
          }}
        />{" "}
        {t("triage.bulk.all")}
      </label>
      <span className={styles.meta} aria-live="polite">
        {shown.length > 0 ? t("triage.bulk.selected", { count: shown.length }) : done}
      </span>
      {shown.length > 0 && (
        <div className={styles.row}>
          <Link to="/redaction/nouveau" search={{ items: shown.join(",") }} className={styles.primary}>
            {t("triage.bulk.brief")}
          </Link>
          {ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => {
                triage.mutate(
                  { itemIds: shown, action },
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
      {triage.error !== null && (
        <span role="alert" className={styles.error}>
          {t("errors.generic")}
        </span>
      )}
    </div>
  );
}
