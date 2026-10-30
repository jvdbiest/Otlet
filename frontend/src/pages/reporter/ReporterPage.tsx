// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  conversationsQuery,
  useDeleteConversations,
  useStartConversation,
  type ConversationSummaryView,
} from "../../reporter.ts";
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

/** The recent conversations, to open or to delete: one by one, or all of them. */
function Recent({ workspaceId, conversations }: { workspaceId: string; conversations: ConversationSummaryView[] }) {
  const { t } = useTranslation();
  const remove = useDeleteConversations(workspaceId);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  // A conversation deleted elsewhere is no longer chosen.
  const chosen = selected.filter((id) => conversations.some((conversation) => conversation.id === id));
  const all = conversations.length > 0 && chosen.length === conversations.length;
  const choose = (next: string[]) => {
    setSelected(next);
    setConfirming(false);
  };
  return (
    <>
      {conversations.length === 0 && <p className={styles.meta}>{t("reporter.none")}</p>}
      {conversations.length > 0 && (
        <p className={styles.row} style={{ flexWrap: "wrap" }}>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={all}
              onChange={(event) => {
                choose(event.target.checked ? conversations.map((conversation) => conversation.id) : []);
              }}
            />{" "}
            {t("reporter.selectAll", { count: conversations.length })}
          </label>
          {chosen.length > 0 && !confirming && (
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setConfirming(true);
              }}
            >
              {t("reporter.deleteChosen", { count: chosen.length })}
            </button>
          )}
          {chosen.length > 0 && confirming && (
            <>
              <span>{t("reporter.deleteConfirm", { count: chosen.length })}</span>
              <button
                type="button"
                className={styles.danger}
                disabled={remove.isPending}
                onClick={() => {
                  remove.mutate(chosen, {
                    onSuccess: () => {
                      choose([]);
                    },
                  });
                }}
              >
                {t("reporter.deleteYes")}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  setConfirming(false);
                }}
              >
                {t("reporter.deleteNo")}
              </button>
            </>
          )}
        </p>
      )}
      {remove.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, remove.error)}
        </p>
      )}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {conversations.map((conversation) => (
          <li key={conversation.id} className={styles.row}>
            <input
              type="checkbox"
              aria-label={t("reporter.selectOne", { title: conversation.title })}
              checked={chosen.includes(conversation.id)}
              onChange={(event) => {
                choose(
                  event.target.checked
                    ? [...chosen, conversation.id]
                    : chosen.filter((id) => id !== conversation.id),
                );
              }}
            />
            <Link to="/reporter/$conversationId" params={{ conversationId: conversation.id }}>
              {conversation.title}
            </Link>
            {conversation.created_at !== null && (
              <span className={styles.meta}>{formatDate(conversation.created_at)}</span>
            )}
          </li>
        ))}
      </ul>
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
        {recent.data !== undefined && <Recent workspaceId={workspaceId} conversations={recent.data} />}
      </section>
    </>
  );
}
