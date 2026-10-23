// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import {
  backupsQuery,
  downloadUrl,
  useBackupNow,
  useSaveSchedule,
  type BackupView,
  type BackupsView,
  type ScheduleView,
} from "../../backups.ts";
import { sessionQuery } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { SettingsTabs } from "./SettingsTabs.tsx";

function size(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) {
    return "—";
  }
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1).replace(".", ",")} ${units[unit] ?? "o"}`;
}

/** The hour of the administrator for an hour in UTC, and back (the schedule is kept in UTC). */
const OFFSET_HOURS = -new Date().getTimezoneOffset() / 60;
const toLocal = (hourUtc: number) => (((hourUtc + OFFSET_HOURS) % 24) + 24) % 24;
const toUtc = (hourLocal: number) => (((hourLocal - OFFSET_HOURS) % 24) + 24) % 24;

function Destination({ view }: { view: BackupsView }) {
  const { t } = useTranslation();
  const { state } = view;
  return (
    <section className={styles.panel} aria-labelledby="backups-destination">
      <h2 id="backups-destination">{t("backups.destination.title")}</h2>
      {!state.configured ? (
        <p className={styles.warning}>{t("backups.destination.none")}</p>
      ) : state.checked_at === null ? (
        <p className={styles.warning}>{t("backups.destination.noService")}</p>
      ) : (
        <>
          <p role="status" className={state.writable ? styles.success : styles.error}>
            {state.writable
              ? t("backups.destination.ok", { free: size(state.free_bytes), total: size(state.total_bytes) })
              : t("backups.destination.ko", { error: state.error ?? "" })}
          </p>
          <p className={styles.meta}>{t("backups.destination.checked", { date: formatDate(state.checked_at) })}</p>
        </>
      )}
      <p className={state.encrypted ? styles.meta : styles.warning}>
        {state.encrypted ? t("backups.encrypted") : t("backups.notEncrypted")}
      </p>
    </section>
  );
}

function Schedule({ schedule }: { schedule: ScheduleView }) {
  const { t } = useTranslation();
  const save = useSaveSchedule();
  const [draft, setDraft] = useState<ScheduleView>(schedule);
  const [saved, setSaved] = useState(false);
  return (
    <section className={styles.panel} aria-labelledby="backups-schedule">
      <h2 id="backups-schedule">{t("backups.schedule.title")}</h2>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(draft, {
            onSuccess: () => {
              setSaved(true);
            },
          });
        }}
      >
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => {
              setDraft({ ...draft, enabled: event.target.checked });
              setSaved(false);
            }}
          />{" "}
          {t("backups.schedule.enabled")}
        </label>
        <p className={styles.field}>
          <label htmlFor="backup-hour">{t("backups.schedule.hour")}</label>
          <select
            id="backup-hour"
            value={toLocal(draft.hour_utc)}
            onChange={(event) => {
              setDraft({ ...draft, hour_utc: toUtc(Number(event.target.value)) });
              setSaved(false);
            }}
          >
            {Array.from({ length: 24 }, (_, hour) => (
              <option key={hour} value={hour}>
                {t("backups.schedule.at", { hour })}
              </option>
            ))}
          </select>
        </p>
        <p className={styles.field}>
          <label htmlFor="backup-daily">{t("backups.schedule.daily")}</label>
          <input
            id="backup-daily"
            type="number"
            min={1}
            max={60}
            value={draft.daily}
            onChange={(event) => {
              setDraft({ ...draft, daily: Number(event.target.value) });
              setSaved(false);
            }}
          />
        </p>
        <p className={styles.field}>
          <label htmlFor="backup-weekly">{t("backups.schedule.weekly")}</label>
          <input
            id="backup-weekly"
            type="number"
            min={0}
            max={52}
            value={draft.weekly}
            onChange={(event) => {
              setDraft({ ...draft, weekly: Number(event.target.value) });
              setSaved(false);
            }}
          />
        </p>
        <p className={styles.row}>
          <button type="submit" className={styles.primary} disabled={save.isPending}>
            {t("backups.schedule.save")}
          </button>
          {saved && (
            <span role="status" className={styles.meta}>
              {t("backups.schedule.saved")}
            </span>
          )}
          {save.error !== null && (
            <span role="alert" className={styles.error}>
              {errorText(t, save.error)}
            </span>
          )}
        </p>
      </form>
    </section>
  );
}

function BackupRow({ backup }: { backup: BackupView }) {
  const { t } = useTranslation();
  const totals = backup.totals;
  return (
    <tr>
      <td>{formatDate(backup.created_at)}</td>
      <td>{t(`backups.reasons.${backup.reason as "manual" | "scheduled" | "startup" | "before-restore"}`)}</td>
      <td>
        {backup.verified ? (
          <span className={styles.success}>{t("backups.verified")}</span>
        ) : (
          <span className={styles.error} title={backup.problems.join("\n")}>
            {t("backups.problems", { count: backup.problems.length })}
          </span>
        )}
      </td>
      <td>
        {t("backups.contents", {
          briefs: totals.briefs ?? 0,
          articles: totals.articles ?? 0,
          media: totals.media ?? 0,
        })}
      </td>
      <td>
        {size(backup.database_bytes + backup.files_bytes)}
        <br />
        <span className={styles.meta}>{t("backups.newFiles", { count: backup.files_new })}</span>
      </td>
      <td>
        <a href={downloadUrl(backup.name)} download>
          {t("backups.download")}
        </a>
      </td>
    </tr>
  );
}

/** Réglages › Sauvegardes (F08, ADR-0042): where the backups go and whether that works, when
 * they are taken, « Sauvegarder maintenant », and every backup, checked, to download. */
export function BackupsPage() {
  const { t } = useTranslation();
  const session = useQuery(sessionQuery);
  const isAdmin = session.data?.user.is_instance_admin === true;
  const view = useQuery({ ...backupsQuery, enabled: isAdmin });
  const now = useBackupNow();
  if (!isAdmin) {
    return <p role="alert">{t("backups.adminOnly")}</p>;
  }
  if (view.data === undefined) {
    return view.error !== null ? <p role="alert">{errorText(t, view.error)}</p> : <p>{t("app.loading")}</p>;
  }
  const { request, state } = view.data;
  const busy = state.running || request?.status === "pending" || request?.status === "running";
  return (
    <div className={styles.article}>
      <h1>{t("settings.title")}</h1>
      <SettingsTabs />
      <p className={styles.help}>{t("backups.intro")}</p>
      <Destination view={view.data} />
      <Schedule key={JSON.stringify(view.data.schedule)} schedule={view.data.schedule} />
      <section className={styles.panel} aria-labelledby="backups-list">
        <h2 id="backups-list">{t("backups.list.title")}</h2>
        <p className={styles.row}>
          <button
            type="button"
            className={styles.primary}
            disabled={busy || now.isPending || !state.writable}
            onClick={() => {
              now.mutate();
            }}
          >
            {t("backups.now")}
          </button>
          <span role="status" className={styles.meta}>
            {busy
              ? t("backups.running")
              : request?.status === "failed"
                ? t("backups.failed", { error: request.error ?? "" })
                : request?.status === "done"
                  ? t("backups.done", { date: formatDate(request.requested_at) })
                  : ""}
          </span>
          {now.error !== null && (
            <span role="alert" className={styles.error}>
              {now.error instanceof ApiError && now.error.detail === "already_running"
                ? t("backups.running")
                : errorText(t, now.error)}
            </span>
          )}
        </p>
        {state.last_error !== null && <p className={styles.error}>{t("backups.lastError", { error: state.last_error })}</p>}
        {view.data.backups.length === 0 ? (
          <p className={styles.help}>{t("backups.list.empty")}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("backups.list.date")}</th>
                <th>{t("backups.list.reason")}</th>
                <th>{t("backups.list.check")}</th>
                <th>{t("backups.list.contents")}</th>
                <th>{t("backups.list.size")}</th>
                <th>
                  <span className="visually-hidden">{t("backups.download")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {view.data.backups.map((backup) => (
                <BackupRow key={backup.name} backup={backup} />
              ))}
            </tbody>
          </table>
        )}
        <p className={styles.help}>{t("backups.restore")}</p>
      </section>
    </div>
  );
}
