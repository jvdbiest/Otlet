// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useCheckProximity, useOverrideProximity, type ArticleView, type VersionView } from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

interface Passage {
  paragraph: string;
  sentence: string;
  source_sentence: string;
}

interface CheckedSource {
  title: string;
  too_close: boolean;
  passages: Passage[];
}

/** How close a version is to its sources (U05, ADR-0046). A version too close does not go out
 * unless its author says why (Joël, 2026-11-01): a false alarm must not force a rewrite. This says
 * nothing of its fidelity to the sources. */
export function Proximity({
  workspaceId,
  article,
  version,
  anchor,
}: {
  workspaceId: string;
  article: ArticleView;
  version: VersionView;
  anchor: (start: string) => string | undefined;
}) {
  const { t } = useTranslation();
  const override = useOverrideProximity(workspaceId);
  const [reason, setReason] = useState("");
  const { mutate: askCheck } = useCheckProximity(workspaceId);
  // A version written before U05, or whose check was lost, is checked when it is read.
  const unchecked = article.brief_id !== null && version.proximity === null;
  useEffect(() => {
    if (unchecked) {
      askCheck({ articleId: article.id, number: version.number });
    }
  }, [unchecked, askCheck, article.id, version.number]);
  if (article.brief_id === null) {
    return null;
  }
  const report = version.proximity as { status?: string; sources?: CheckedSource[] } | null;
  if (report === null) {
    return <p className={styles.notice}>{t("proximity.pending")}</p>;
  }
  if (report.status === "failed") {
    return <p className={styles.notice}>{t("proximity.failed")}</p>;
  }
  const close = (report.sources ?? []).filter((source) => source.too_close);
  if (close.length === 0) {
    return null;
  }
  const kept = version.proximity_override as { reason?: string; at?: string } | null;
  return (
    <div role="note" className={styles.warning}>
      <p>
        <strong>{t("draft.warning")}</strong>
      </p>
      {kept !== null ? (
        <p>{t("proximity.overridden", { date: formatDate(kept.at ?? ""), reason: kept.reason ?? "" })}</p>
      ) : (
        <p>{t("proximity.blocked", { count: close.length })}</p>
      )}
      {close.map((source) => (
        <details key={source.title}>
          <summary>{source.title}</summary>
          <ul>
            {source.passages.map((passage, index) => {
              const link = anchor(passage.paragraph);
              return (
                <li key={index}>
                  {link === undefined ? passage.sentence : <a href={`#${link}`}>{passage.sentence}</a>}
                  <br />
                  <span className={styles.meta}>{t("proximity.source", { sentence: passage.source_sentence })}</span>
                </li>
              );
            })}
          </ul>
        </details>
      ))}
      <p className={styles.meta}>{t("proximity.notFidelity")}</p>
      {kept === null && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            override.mutate({ articleId: article.id, number: version.number, reason });
          }}
        >
          <label>
            {t("proximity.justification")}
            <br />
            <textarea
              rows={3}
              style={{ width: "100%" }}
              value={reason}
              placeholder={t("proximity.hint")}
              onChange={(event) => {
                setReason(event.target.value);
              }}
            />
          </label>
          <p className={styles.row}>
            <button type="submit" className={styles.button} disabled={override.isPending || reason.trim().length < 10}>
              {t("proximity.submit")}
            </button>
            {override.error !== null && (
              <span role="alert" className={styles.error}>
                {errorText(t, override.error)}
              </span>
            )}
          </p>
        </form>
      )}
    </div>
  );
}
