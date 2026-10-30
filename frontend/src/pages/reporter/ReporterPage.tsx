// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { conversationsQuery, useStartConversation } from "../../reporter.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

/** The Reporter (ADR-0044): a first question starts a conversation; the recent ones. */
export function ReporterPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Reporter workspaceId={workspaceId} />;
}

/** « Lire avant de répondre »: off by default, the model reads the set before it is shown. */
export function ReadFirst({ read, onChange }: { read: boolean; onChange: (read: boolean) => void }) {
  const { t } = useTranslation();
  return (
    <>
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={read}
          onChange={(event) => {
            onChange(event.target.checked);
          }}
        />{" "}
        {t("reporter.reading.first")}
      </label>
      <p className={styles.help}>{t("reporter.reading.firstHelp")}</p>
    </>
  );
}

function Reporter({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const start = useStartConversation(workspaceId);
  const recent = useQuery(conversationsQuery(workspaceId));
  const [question, setQuestion] = useState("");
  const [read, setRead] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  return (
    <>
      <h1>{t("reporter.title")}</h1>
      <p>{t("reporter.intro")}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          start.mutate({ question: question.trim(), read, date_from: from || null, date_to: to || null }, {
            onSuccess: (conversation) => {
              void navigate({ to: "/reporter/$conversationId", params: { conversationId: conversation.id } });
            },
          });
        }}
      >
        <label className={styles.field}>
          <span>{t("reporter.question")}</span>
          <input
            value={question}
            maxLength={500}
            onChange={(event) => {
              setQuestion(event.target.value);
            }}
          />
        </label>
        <p className={styles.help}>{t("reporter.examples")}</p>
        <p className={styles.row}>
          <label className={styles.field}>
            <span>{t("reporter.dateFrom")}</span>
            <input
              type="date"
              value={from}
              max={to || undefined}
              onChange={(event) => {
                setFrom(event.target.value);
              }}
            />
          </label>
          <label className={styles.field}>
            <span>{t("reporter.dateTo")}</span>
            <input
              type="date"
              value={to}
              min={from || undefined}
              onChange={(event) => {
                setTo(event.target.value);
              }}
            />
          </label>
        </p>
        <p className={styles.help}>{t("reporter.datesHelp")}</p>
        <ReadFirst read={read} onChange={setRead} />
        <p className={styles.row}>
          <button type="submit" className={styles.primary} disabled={question.trim() === "" || start.isPending}>
            {t("reporter.start")}
          </button>
        </p>
        {start.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, start.error)}
          </p>
        )}
      </form>
      <section className={styles.panel} aria-labelledby="reporter-recent">
        <h2 id="reporter-recent">{t("reporter.recent")}</h2>
        {recent.data?.length === 0 && <p className={styles.meta}>{t("reporter.none")}</p>}
        <ul>
          {recent.data?.map((conversation) => (
            <li key={conversation.id}>
              <Link to="/reporter/$conversationId" params={{ conversationId: conversation.id }}>
                {conversation.title}
              </Link>{" "}
              {conversation.created_at !== null && (
                <span className={styles.meta}>{formatDate(conversation.created_at)}</span>
              )}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
