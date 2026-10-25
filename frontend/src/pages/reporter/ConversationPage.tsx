// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  conversationQuery,
  useAsk,
  useSetTerms,
  type ConversationView,
  type FactView,
  type TurnCandidate,
  type TurnView,
} from "../../reporter.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

const BRIEF_MAX = 20;
const SHOWN_AT_ONCE = 8;
const CHANGES_SET: readonly string[] = ["chercher", "restreindre", "élargir"];

/** A conversation of the Reporter (ADR-0044): each question and its answer, a set of items or
 * lines of fact cited by source, then the next question. */
export function ConversationPage({ conversationId }: { conversationId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Conversation workspaceId={workspaceId} conversationId={conversationId} />;
}

function Conversation({ workspaceId, conversationId }: { workspaceId: string; conversationId: string }) {
  const { t } = useTranslation();
  const conversation = useQuery(conversationQuery(workspaceId, conversationId));
  if (conversation.data === undefined) {
    return conversation.error !== null ? (
      <p role="alert">{errorText(t, conversation.error)}</p>
    ) : (
      <p>{t("app.loading")}</p>
    );
  }
  const data = conversation.data;
  const last = data.turns.at(-1);
  return (
    <>
      <p>
        <Link to="/reporter">{t("reporter.back")}</Link>
      </p>
      <h1>{data.title}</h1>
      {data.turns.map((turn) => (
        <Turn key={turn.id} workspaceId={workspaceId} conversation={data} turn={turn} last={turn.id === last?.id} />
      ))}
      <Ask
        workspaceId={workspaceId}
        conversationId={conversationId}
        busy={data.turns.some((turn) => turn.status === "pending")}
      />
    </>
  );
}

function Ask({ workspaceId, conversationId, busy }: { workspaceId: string; conversationId: string; busy: boolean }) {
  const { t } = useTranslation();
  const ask = useAsk(workspaceId, conversationId);
  const [question, setQuestion] = useState("");
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        ask.mutate(question.trim(), {
          onSuccess: () => {
            setQuestion("");
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
      <p className={styles.row}>
        <button type="submit" className={styles.primary} disabled={busy || question.trim() === "" || ask.isPending}>
          {t("reporter.ask")}
        </button>
      </p>
      {ask.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, ask.error)}
        </p>
      )}
    </form>
  );
}

function Turn({
  workspaceId,
  conversation,
  turn,
  last,
}: {
  workspaceId: string;
  conversation: ConversationView;
  turn: TurnView;
  last: boolean;
}) {
  const { t } = useTranslation();
  return (
    <section className={styles.panel} aria-label={turn.question}>
      <p>
        <strong>{turn.question}</strong>
      </p>
      {turn.status === "pending" && (
        <p role="status" className={styles.meta}>
          {t("reporter.pending")}
        </p>
      )}
      {turn.status === "failed" && <p className={styles.warning}>{t("reporter.failed", { error: turn.error ?? "" })}</p>}
      {turn.status === "done" && (
        <>
          <p className={styles.meta}>
            {turn.operation !== null && t(`reporter.operation.${turn.operation}`)}
            {turn.language !== null && ` · ${t("reporter.language", { language: turn.language })}`}
            {turn.model !== null && ` · ${t("reporter.model", { model: turn.model })}`}
          </p>
          {/* A fact, a sort or an action reads the set of the previous answer: its terms are there. */}
          {(turn.operation === null || CHANGES_SET.includes(turn.operation)) && (
            <Terms workspaceId={workspaceId} conversationId={conversation.id} turn={turn} editable={last} />
          )}
          {turn.operation === "fait" ? (
            <Fact turn={turn} fact={turn.fact} />
          ) : (
            <ItemSet turn={turn} title={conversation.title} last={last} />
          )}
        </>
      )}
    </section>
  );
}

/** The terms searched, as the author can check and change them (last set only). */
function Terms({
  workspaceId,
  conversationId,
  turn,
  editable,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  editable: boolean;
}) {
  const { t } = useTranslation();
  const setTerms = useSetTerms(workspaceId, conversationId);
  const [drafts, setDrafts] = useState<string[] | null>(null);
  if (turn.concepts.length === 0) {
    return null;
  }
  if (drafts !== null) {
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setTerms.mutate(
            {
              turnId: turn.id,
              concepts: turn.concepts.map((c, n) => ({
                name: c.name,
                terms: (drafts[n] ?? "")
                  .split(",")
                  .map((term) => term.trim())
                  .filter((term) => term !== ""),
              })),
            },
            {
              onSuccess: () => {
                setDrafts(null);
              },
            },
          );
        }}
      >
        {turn.concepts.map((concept, index) => (
          <p key={concept.name + String(index)} className={styles.row}>
            {index > 0 && <strong>{t("assistant.terms.and")}</strong>}
            <input
              aria-label={t("assistant.terms.concept", { name: concept.name })}
              style={{ flex: "1 1 30rem" }}
              value={drafts[index] ?? ""}
              onChange={(event) => {
                setDrafts(drafts.map((d, n) => (n === index ? event.target.value : d)));
              }}
            />
          </p>
        ))}
        <p className={styles.row}>
          <button type="submit" className={styles.primary} disabled={setTerms.isPending}>
            {t("reporter.search")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setDrafts(null);
            }}
          >
            {t("reporter.cancel")}
          </button>
        </p>
        {setTerms.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, setTerms.error)}
          </p>
        )}
      </form>
    );
  }
  return (
    <div>
      {turn.concepts.map((concept, index) => (
        <div key={concept.name + String(index)} className={styles.row} style={{ flexWrap: "wrap" }}>
          {index > 0 && <strong>{t("assistant.terms.and")}</strong>}
          {[...concept.terms, ...concept.added].map((term) => {
            const general = concept.general.includes(term);
            return (
              <span
                key={term}
                className={styles.chip}
                style={general ? { opacity: 0.5, textDecoration: "line-through" } : undefined}
                title={
                  general
                    ? t("assistant.terms.general")
                    : concept.added.includes(term)
                      ? t("assistant.terms.fromGlossary")
                      : undefined
                }
              >
                {term}
                {term in concept.counts && <small> · {concept.counts[term]}</small>}
              </span>
            );
          })}
        </div>
      ))}
      {editable && turn.operation !== "fait" && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setDrafts(turn.concepts.map((c) => [...c.terms, ...c.added].join(", ")));
            }}
          >
            {t("reporter.editTerms")}
          </button>
        </p>
      )}
    </div>
  );
}

/** The set of the answer: its count opens the items; after a sort, by verdict. */
function ItemSet({ turn, title, last }: { turn: TurnView; title: string; last: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(last && turn.candidates.length <= SHOWN_AT_ONCE);
  const sorted = turn.candidates.some((c) => c.judged !== null);
  const kept = sorted ? turn.candidates.filter((c) => c.judged?.verdict === "traite") : turn.candidates;
  const chosen = (kept.length > 0 ? kept : turn.candidates).slice(0, BRIEF_MAX);
  const count = (verdict: string) => turn.candidates.filter((c) => c.judged?.verdict === verdict).length;
  return (
    <>
      <p className={styles.row}>
        <strong>{t("reporter.set", { count: turn.candidates.length })}</strong>
        {turn.candidates.length > 0 && (
          <button
            type="button"
            className={styles.button}
            aria-expanded={open}
            onClick={() => {
              setOpen(!open);
            }}
          >
            {open ? t("reporter.hideSet") : t("reporter.showSet")}
          </button>
        )}
      </p>
      {sorted && (
        <p className={styles.meta}>
          {t("reporter.sorted", { kept: count("traite"), check: count("proche"), aside: count("hors_sujet") })}
        </p>
      )}
      {turn.candidates.length === 0 && <p className={styles.notice}>{t("reporter.emptySet")}</p>}
      {open && <Items candidates={sorted ? [...kept, ...turn.candidates.filter((c) => !kept.includes(c))] : turn.candidates} />}
      {last && chosen.length > 0 && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              void navigate({
                to: "/redaction/nouveau",
                search: { items: chosen.map((c) => c.id).join(","), title, angle: "" },
              });
            }}
          >
            {chosen.length < turn.candidates.length
              ? t("reporter.toBriefFirst", { count: chosen.length })
              : t("reporter.toBrief", { count: chosen.length })}
          </button>
        </p>
      )}
    </>
  );
}

function Items({ candidates }: { candidates: TurnCandidate[] }) {
  const { t } = useTranslation();
  return (
    <ul style={{ listStyle: "none", padding: 0 }}>
      {candidates.map((candidate) => (
        <li key={candidate.id} style={{ margin: "0.5rem 0" }}>
          <span className={styles.meta}>[{(candidate.language ?? "?").slice(0, 2).toUpperCase()}]</span>{" "}
          <Link to="/veille/elements/$itemId" params={{ itemId: candidate.id }}>
            {candidate.title}
          </Link>
          <br />
          <span className={styles.meta}>
            {[candidate.publisher, formatDate(candidate.dated)].filter(Boolean).join(" · ")}
          </span>
          {candidate.judged !== null && (
            <>
              <br />
              <span className={styles.help}>
                {t(`assistant.groups.${candidate.judged.verdict}`, { count: 1 })} ·{" "}
                {candidate.judged.by_model
                  ? t("assistant.reason", { reason: candidate.judged.reason })
                  : candidate.judged.reason}
              </span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The lines of a fact, each with its source and passage, and the agreement Otlet computed. */
function Fact({ turn, fact }: { turn: TurnView; fact: FactView | null }) {
  const { t } = useTranslation();
  if (fact === null) {
    return <p className={styles.warning}>{t("reporter.fact.noModel", { error: turn.error ?? "" })}</p>;
  }
  const names = (n: number) => fact.lines[n];
  return (
    <>
      <h3>{t("reporter.fact.title", { count: fact.read.length })}</h3>
      {fact.lines.length === 0 ? (
        <p className={styles.notice}>{t("reporter.fact.none")}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">{t("reporter.fact.source")}</th>
              <th scope="col">{t("reporter.fact.figure")}</th>
              <th scope="col">{t("reporter.fact.measure")}</th>
              <th scope="col">{t("reporter.fact.when")}</th>
              <th scope="col">{t("reporter.fact.where")}</th>
              <th scope="col">{t("reporter.fact.passage")}</th>
            </tr>
          </thead>
          <tbody>
            {fact.lines.map((line, index) => (
              <tr key={String(index) + line.item_id}>
                <td>
                  <Link to="/veille/elements/$itemId" params={{ itemId: line.item_id }}>
                    {line.publisher}
                  </Link>
                </td>
                <td>
                  <strong>{line.figure}</strong>
                </td>
                <td>{line.measure}</td>
                <td>{line.when}</td>
                <td>{line.where}</td>
                <td>
                  <q>{line.passage}</q>
                  {!line.figure_in_passage && (
                    <>
                      <br />
                      <span className={styles.warning}>{t("reporter.fact.outside")}</span>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p>
        <strong>{t(`reporter.fact.agreement.${fact.agreement}`)}</strong>
      </p>
      {fact.compared.length > 0 && (
        <ul>
          {fact.compared.map((pair) => {
            const first = names(pair.first);
            const second = names(pair.second);
            if (first === undefined || second === undefined) {
              return null;
            }
            return (
              <li key={`${String(pair.first)}-${String(pair.second)}`}>
                {first.publisher} {first.figure} {pair.same ? "=" : "≠"} {second.publisher} {second.figure} ·{" "}
                {pair.same ? t("reporter.fact.same") : t("reporter.fact.different")}
              </li>
            );
          })}
        </ul>
      )}
      <p className={styles.help}>{t("reporter.fact.agreementHelp")}</p>
      {fact.dropped > 0 && <p className={styles.meta}>{t("reporter.fact.dropped", { count: fact.dropped })}</p>}
      {fact.conclusion !== "" && fact.lines.length > 0 && (
        <p className={styles.meta}>{t("reporter.fact.conclusion", { text: fact.conclusion })}</p>
      )}
    </>
  );
}
