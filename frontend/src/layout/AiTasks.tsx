// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { aiTasksQuery, useCancelAllAiTasks } from "../aiTasks.ts";
import css from "./AiTasks.module.css";

const styles = css as Record<"tasks" | "count" | "cancel", string>;

/** « Tâche(s) IA en cours » at the foot of the main navigation, and their cancellation. */
export function AiTasks({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const tasks = useQuery(aiTasksQuery(workspaceId));
  const cancel = useCancelAllAiTasks(workspaceId);
  const count = tasks.data?.length ?? 0;
  return (
    <div className={styles.tasks}>
      <p role="status" className={styles.count}>
        {t("aiTasks.count", { count })}
      </p>
      {count > 0 && (
        <button
          type="button"
          className={styles.cancel}
          disabled={cancel.isPending}
          onClick={() => {
            cancel.mutate();
          }}
        >
          {t("aiTasks.cancelAll")}
        </button>
      )}
    </div>
  );
}
