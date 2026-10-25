// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { dossiersQuery, glossaryQuery, useDeleteEntry, useSaveEntry, useStartDossier } from "../../assistant.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText, formatDate } from "./labels.ts";
import { styles } from "./styles.ts";

const PERIODS = [7, 30, 0] as const; // 0: every date

/** Veille › Assistant (A1b-1, ADR-0043): a subject, and the matter of the Veille found for it;
 * the recent dossiers; the glossary that widens every search. */
export function AssistantPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Assistant workspaceId={workspaceId} />;
}

function Assistant({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const start = useStartDossier(workspaceId);
  const recent = useQuery(dossiersQuery(workspaceId));
  const [subject, setSubject] = useState("");
  const [angle, setAngle] = useState("");
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30);
  return (
    <>
      <p className={styles.help}>{t("assistant.intro")}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          start.mutate(
            { subject, angle, days: days === 0 ? null : days, concepts: [] },
            {
              onSuccess: (dossier) => {
                void navigate({ to: "/veille/assistant/$dossierId", params: { dossierId: dossier.id } });
              },
            },
          );
        }}
      >
        <div className={styles.field}>
          <label htmlFor="assistant-subject">{t("assistant.subject")}</label>
          <input
            id="assistant-subject"
            required
            maxLength={200}
            placeholder={t("assistant.subjectExample")}
            value={subject}
            onChange={(event) => {
              setSubject(event.target.value);
            }}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="assistant-angle">{t("assistant.angle")}</label>
          <input
            id="assistant-angle"
            maxLength={500}
            placeholder={t("assistant.angleExample")}
            value={angle}
            onChange={(event) => {
              setAngle(event.target.value);
            }}
          />
          <span className={styles.help}>{t("assistant.angleHelp")}</span>
        </div>
        <fieldset className={styles.choices}>
          <legend>{t("assistant.period")}</legend>
          {PERIODS.map((value) => (
            <label key={value}>
              <input
                type="radio"
                name="assistant-period"
                checked={days === value}
                onChange={() => {
                  setDays(value);
                }}
              />{" "}
              {t(value === 7 ? "assistant.periods.7" : value === 30 ? "assistant.periods.30" : "assistant.periods.0")}
            </label>
          ))}
        </fieldset>
        {start.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, start.error)}
          </p>
        )}
        <p className={styles.row}>
          <button type="submit" className={styles.primary} disabled={start.isPending || subject.trim() === ""}>
            {t("assistant.explore")}
          </button>
        </p>
      </form>
      {(recent.data ?? []).length > 0 && (
        <section className={styles.panel} aria-labelledby="assistant-recent">
          <h2 id="assistant-recent">{t("assistant.recent")}</h2>
          <ul>
            {(recent.data ?? []).map((dossier) => (
              <li key={dossier.id}>
                <Link to="/veille/assistant/$dossierId" params={{ dossierId: dossier.id }}>
                  {dossier.subject}
                </Link>{" "}
                <span className={styles.meta}>
                  {dossier.created_at === null ? "" : formatDate(dossier.created_at)} ·{" "}
                  {dossier.status === "done"
                    ? t("assistant.candidates", { count: dossier.candidates })
                    : t("assistant.running")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Glossary workspaceId={workspaceId} />
    </>
  );
}

/** The glossary of the workspace: terms that mean the same, in any language (ADR-0043 §3). */
function Glossary({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const entries = useQuery(glossaryQuery(workspaceId));
  const save = useSaveEntry(workspaceId);
  const remove = useDeleteEntry(workspaceId);
  const [draft, setDraft] = useState("");
  const terms = draft
    .split(/[,;\n]/)
    .map((term) => term.trim())
    .filter((term) => term !== "");
  return (
    <section className={styles.panel} aria-labelledby="assistant-glossary">
      <h2 id="assistant-glossary">{t("assistant.glossary.title")}</h2>
      <p className={styles.help}>{t("assistant.glossary.help")}</p>
      {(entries.data ?? []).length === 0 ? (
        <p className={styles.meta}>{t("assistant.glossary.empty")}</p>
      ) : (
        <ul>
          {(entries.data ?? []).map((entry) => (
            <li key={entry.id} className={styles.row}>
              <span>{entry.terms.join(" = ")}</span>
              <button
                type="button"
                className={styles.button}
                aria-label={t("assistant.glossary.delete", { terms: entry.terms.join(", ") })}
                onClick={() => {
                  remove.mutate(entry.id);
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className={styles.row}
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(
            { entryId: null, terms },
            {
              onSuccess: () => {
                setDraft("");
              },
            },
          );
        }}
      >
        <label htmlFor="glossary-new" className="visually-hidden">
          {t("assistant.glossary.new")}
        </label>
        <input
          id="glossary-new"
          style={{ flex: "1 1 20rem" }}
          placeholder={t("assistant.glossary.example")}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
        />
        <button type="submit" className={styles.button} disabled={terms.length < 2 || save.isPending}>
          {t("assistant.glossary.add")}
        </button>
      </form>
      {save.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, save.error)}
        </p>
      )}
    </section>
  );
}
