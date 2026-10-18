// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { draftQuery, useClearDetails, useGenerateDraft, type GenerationView } from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { DocumentView, type PlatformDocument } from "./DocumentView.tsx";
import { GenerationDetails } from "./GenerationDetails.tsx";

const FAILURES = [
  "no_profile",
  "no_sources",
  "budget",
  "refused",
  "invalid",
  "out_of_room",
  "quota",
  "unavailable",
  "blocked",
] as const;

function failure(generation: GenerationView): (typeof FAILURES)[number] {
  return FAILURES.find((code) => code === generation.error) ?? "unavailable";
}

/** A list of the details: the sections of a synthesis still on one source, the paragraphs
 * that repeat another. */
function listed(details: Record<string, unknown>, key: "lone_sections" | "repeated_paragraphs"): string[] {
  const found = details[key];
  return Array.isArray(found) ? found.filter((h): h is string => typeof h === "string") : [];
}

/** The draft of a brief (U04): generate it, follow the generation, read its versions. */
export function DraftPanel({ workspaceId, briefId }: { workspaceId: string; briefId: string }) {
  const { t } = useTranslation();
  const draft = useQuery(draftQuery(workspaceId, briefId));
  const generate = useGenerateDraft(workspaceId, briefId);
  const clear = useClearDetails(workspaceId, briefId);
  const [confirming, setConfirming] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  if (draft.data === undefined) {
    return null;
  }
  const { article, generation } = draft.data;
  const running = generation?.status === "running";
  const versions = article?.versions ?? [];
  const shown = versions.find((v) => v.number === chosen) ?? versions.at(-1);
  return (
    <section className={styles.panel} aria-labelledby="draft-title">
      <h2 id="draft-title">{t("draft.title")}</h2>
      <p className={styles.help}>{t("draft.help")}</p>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.primary}
          disabled={running || generate.isPending}
          onClick={() => {
            generate.mutate(undefined, {
              onSuccess: () => {
                setChosen(null);
              },
            });
          }}
        >
          {versions.length === 0 ? t("draft.generate") : t("draft.again")}
        </button>
        {running && (
          <span role="status" className={styles.meta}>
            {t("draft.running", { since: formatDate(generation.created_at) })}
          </span>
        )}
      </p>
      {generate.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, generate.error)}
        </p>
      )}
      {generation?.status === "failed" && (
        <div role="alert" className={styles.warning}>
          <p>{t(`draft.failed.${failure(generation)}`)}</p>
          <ul className={styles.journal}>
            {generation.attempts.map((attempt, index) => (
              <li key={index}>
                {String(attempt.provider)} · {String(attempt.model)} · {String(attempt.result)} ·{" "}
                {String(attempt.seconds)} s
              </li>
            ))}
          </ul>
          <GenerationDetails
            details={generation.details}
            heading={t("draft.details.failedHeading", { date: formatDate(generation.created_at) })}
          />
        </div>
      )}
      {shown !== undefined && (
        <>
          <div className={styles.row}>
            {versions.length > 1 && (
              <select
                aria-label={t("draft.version")}
                value={shown.number}
                onChange={(event) => {
                  setChosen(Number(event.target.value));
                }}
              >
                {versions.map((v) => (
                  <option key={v.number} value={v.number}>
                    {t("draft.versionLabel", { number: v.number, date: formatDate(v.created_at) })}
                  </option>
                ))}
              </select>
            )}
            <span className={styles.meta}>
              {shown.origin === "ia"
                ? t("draft.byModel", {
                    number: shown.number,
                    model: shown.model ?? "",
                    provider: shown.provider_kind ?? "",
                    date: formatDate(shown.created_at),
                  })
                : t("draft.byPerson", { number: shown.number, date: formatDate(shown.created_at) })}
            </span>
          </div>
          {shown.context_overflow && (
            <p role="note" className={styles.warning}>
              {t("draft.overflow")}
            </p>
          )}
          {shown.unused_sources.length > 0 && (
            <div role="note" className={styles.warning}>
              <p>{t("draft.unused", { count: shown.unused_sources.length })}</p>
              <ul>
                {shown.unused_sources.map((title) => (
                  <li key={title}>{title}</li>
                ))}
              </ul>
            </div>
          )}
          {listed(shown.details, "lone_sections").length > 0 && (
            <div role="note" className={styles.warning}>
              <p>{t("draft.lone", { count: listed(shown.details, "lone_sections").length })}</p>
              <ul>
                {listed(shown.details, "lone_sections").map((heading) => (
                  <li key={heading}>{heading}</li>
                ))}
              </ul>
            </div>
          )}
          {listed(shown.details, "repeated_paragraphs").length > 0 && (
            <div role="note" className={styles.warning}>
              <p>{t("draft.repeated", { count: listed(shown.details, "repeated_paragraphs").length })}</p>
              <ul>
                {listed(shown.details, "repeated_paragraphs").map((start) => (
                  <li key={start}>{start}</li>
                ))}
              </ul>
            </div>
          )}
          {shown.cut_sources.length > 0 && (
            <p className={styles.notice}>{t("draft.cut", { sources: shown.cut_sources.join(", ") })}</p>
          )}
          <GenerationDetails
            details={shown.details}
            heading={t("draft.details.heading", { number: shown.number, date: formatDate(shown.created_at) })}
          />
          <DocumentView
            document={shown.document as unknown as PlatformDocument}
            title={shown.title}
            prefix={`v${String(shown.number)}`}
          />
        </>
      )}
      {(versions.length > 0 || generation !== null) && (
        <p className={styles.row}>
          {confirming ? (
            <>
              <span>{t("draft.details.confirmClear")}</span>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  clear.mutate(undefined, {
                    onSuccess: () => {
                      setConfirming(false);
                    },
                  });
                }}
              >
                {t("draft.details.clear")}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  setConfirming(false);
                }}
              >
                {t("brief.cancel")}
              </button>
            </>
          ) : (
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => {
                setConfirming(true);
              }}
            >
              {t("draft.details.clearAll")}
            </button>
          )}
        </p>
      )}
    </section>
  );
}
