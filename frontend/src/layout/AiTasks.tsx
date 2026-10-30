// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { aiTasksQuery, useCancelAllAiTasks, type AiTaskView } from "../aiTasks.ts";
import css from "./AiTasks.module.css";

const styles = css as Record<"tasks" | "count" | "cancel" | "bubble" | "kind" | "link", string>;

/** The screen where a task runs. */
function TaskLink({ task }: { task: AiTaskView }) {
  const { t } = useTranslation();
  const text = (
    <>
      <span className={styles.kind}>{t(`aiTasks.kind.${task.kind}`)}</span>
      {task.label}
    </>
  );
  switch (task.kind) {
    case "reporter":
      return (
        <Link className={styles.link} to="/reporter/$conversationId" params={{ conversationId: task.id }}>
          {text}
        </Link>
      );
    case "dossier":
      return (
        <Link className={styles.link} to="/veille/assistant/$dossierId" params={{ dossierId: task.id }}>
          {text}
        </Link>
      );
    case "draft":
      return (
        <Link className={styles.link} to="/redaction/briefs/$briefId" params={{ briefId: task.id }}>
          {text}
        </Link>
      );
    case "check":
      return (
        <Link className={styles.link} to="/reglages">
          {text}
        </Link>
      );
  }
}

/** « Tâche(s) IA en cours » at the foot of the main navigation: over it, a bubble names them,
 * each a link to its screen; and their cancellation. */
export function AiTasks({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const tasks = useQuery(aiTasksQuery(workspaceId));
  const cancel = useCancelAllAiTasks(workspaceId);
  const running = tasks.data ?? [];
  return (
    <div className={styles.tasks}>
      {running.length > 0 && (
        <ul className={styles.bubble} aria-label={t("aiTasks.list")}>
          {running.map((task) => (
            <li key={task.kind + task.id}>
              <TaskLink task={task} />
            </li>
          ))}
        </ul>
      )}
      <p role="status" className={styles.count} tabIndex={running.length > 0 ? 0 : undefined}>
        {t("aiTasks.count", { count: running.length })}
      </p>
      {running.length > 0 && (
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
