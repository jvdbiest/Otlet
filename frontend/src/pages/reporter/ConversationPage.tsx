// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  conversationQuery,
  useAsk,
  useCancelQuestion,
  useReadMore,
  useReconstitute,
  useReconstituteSubject,
  useReadSet,
  useSetTerms,
  type ConversationView,
  type FactView,
  type ReadingView,
  type SentenceView,
  type TurnCandidate,
  type TurnView,
} from "../../reporter.ts";
import { AiButton } from "../../layout/AiButton.tsx";
import { useWorkspaceId } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { ReadFirst } from "./ReporterPage.tsx";

const BRIEF_MAX = 20;
const SHOWN_AT_ONCE = 8;
// The largest set the Reporter keeps (reporter.SET_MAX): reached, the question is too broad.
const SET_MAX = 200;
const CHANGES_SET: readonly string[] = ["chercher", "restreindre", "élargir"];
// From this many items, the main themes are shown at once (Joël, 2026-10-29).
const THEMES_OPEN = 100;

/** « 2026-10-29 » as the reader writes it. */
function formatDay(day: string): string {
  return day.split("-").reverse().join("/");
}

/** A conversation of the Reporter (ADR-0044): each question and its answer, a set of items or
 * lines of fact cited by source, then the next question. */
export function ConversationPage({ conversationId }: { conversationId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Conversation workspaceId={workspaceId} conversationId={conversationId} />;
}

function Conversation({ workspaceId, conversationId }: { workspaceId: string; conversationId: string }) {
  const { t } = useTranslation();
  const conversation = useQuery(conversationQuery(workspaceId, conversationId));
  // The articles chosen for a brief: of the whole conversation, whatever the question asked next.
  const [selected, setSelected] = useState<string[]>([]);
  if (conversation.data === undefined) {
    return conversation.error !== null ? (
      <p role="alert">{errorText(t, conversation.error)}</p>
    ) : (
      <p>{t("app.loading")}</p>
    );
  }
  const data = conversation.data;
  const last = data.turns.at(-1);
  const busy = data.turns.some((turn) => turn.status === "pending");
  return (
    <>
      <p>
        <Link to="/reporter">{t("reporter.back")}</Link>
      </p>
      <h1>{data.title}</h1>
      {data.turns.map((turn) => (
        <Turn
          key={turn.id}
          workspaceId={workspaceId}
          conversation={data}
          turn={turn}
          last={turn.id === last?.id}
          busy={busy}
          selected={selected}
          onSelect={setSelected}
        />
      ))}
      {/* Once used, the reading stays on for the next questions (Joël, 2026-10-29). */}
      <Ask workspaceId={workspaceId} conversationId={conversationId} busy={busy} readBefore={(last?.reading ?? null) !== null} />
    </>
  );
}

function Ask({
  workspaceId,
  conversationId,
  busy,
  readBefore,
}: {
  workspaceId: string;
  conversationId: string;
  busy: boolean;
  readBefore: boolean;
}) {
  const { t } = useTranslation();
  const ask = useAsk(workspaceId, conversationId);
  const cancel = useCancelQuestion(workspaceId, conversationId);
  const [question, setQuestion] = useState("");
  const [read, setRead] = useState(readBefore);
  const failure = ask.error ?? cancel.error;
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        if (busy || question.trim() === "") {
          return;
        }
        ask.mutate({ question: question.trim(), read }, {
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
      <ReadFirst read={read} onChange={setRead} />
      <p className={styles.row}>
        <AiButton
          running={busy}
          cancelling={cancel.isPending}
          onCancel={() => {
            cancel.mutate();
          }}
          type="submit"
          className={styles.primary}
          disabled={question.trim() === "" || ask.isPending}
        >
          {t("reporter.ask")}
        </AiButton>
      </p>
      {failure !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, failure)}
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
  busy,
  selected,
  onSelect,
}: {
  workspaceId: string;
  conversation: ConversationView;
  turn: TurnView;
  last: boolean;
  busy: boolean;
  selected: string[];
  onSelect: (selected: string[]) => void;
}) {
  const { t } = useTranslation();
  return (
    <section className={styles.panel} aria-label={turn.question}>
      <p>
        <strong>{turn.question}</strong>
      </p>
      {turn.status === "pending" && (
        <p role="status" className={styles.meta}>
          {turn.reconstitution?.requested === true
            ? t("reporter.rebuild.pending")
            : turn.reading?.requested === true && turn.operation !== null
              ? t("reporter.reading.pending")
              : t("reporter.pending")}
        </p>
      )}
      {turn.status === "failed" && turn.error === "cancelled" && <p className={styles.notice}>{t("reporter.cancelled")}</p>}
      {turn.status === "failed" && turn.error !== "cancelled" && (
        <p className={styles.warning}>
          {turn.error?.includes("out_of_room") === true
            ? t("reporter.failedRoom")
            : t("reporter.failed", { error: turn.error ?? "" })}
        </p>
      )}
      {turn.status === "done" && (
        <>
          <p className={styles.meta}>
            {turn.operation !== null && t(`reporter.operation.${turn.operation}`)}
            {turn.language !== null && ` · ${t("reporter.language", { language: turn.language })}`}
            {turn.date_from === null && turn.date_to === null && turn.days !== null && ` · ${t("reporter.period", { count: turn.days })}`}
            {(turn.date_from !== null || turn.date_to !== null) &&
              ` · ${t("reporter.dates", { from: turn.date_from === null ? "…" : formatDay(turn.date_from), to: turn.date_to === null ? "…" : formatDay(turn.date_to) })}`}
            {turn.excluded.length > 0 && ` · ${t("reporter.excluded", { terms: turn.excluded.join(", ") })}`}
            {turn.model !== null && ` · ${t("reporter.model", { model: turn.model })}`}
          </p>
          {/* A fact, a sort or an action reads the set of the previous answer: its terms are
          there; asked first, it searched its own set. */}
          {(turn.operation === null || CHANGES_SET.includes(turn.operation) || turn.position === 1) && (
            <>
              <Terms workspaceId={workspaceId} conversationId={conversation.id} turn={turn} editable={last} />
              <Unsearched workspaceId={workspaceId} conversationId={conversation.id} turn={turn} last={last} />
            </>
          )}
          {turn.operation === "fait" ? (
            <Fact workspaceId={workspaceId} conversationId={conversation.id} turn={turn} fact={turn.fact} />
          ) : (
            <ItemSet
              workspaceId={workspaceId}
              conversationId={conversation.id}
              turn={turn}
              title={conversation.title}
              last={last}
              selected={selected}
              onSelect={onSelect}
            />
          )}
          <Reading workspaceId={workspaceId} conversationId={conversation.id} turn={turn} busy={busy} />
          <Rebuild workspaceId={workspaceId} conversationId={conversation.id} turn={turn} busy={busy} />
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

/** Words of the question no term searched: shown, and added to the terms in one click. */
function Unsearched({
  workspaceId,
  conversationId,
  turn,
  last,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  last: boolean;
}) {
  const { t } = useTranslation();
  const setTerms = useSetTerms(workspaceId, conversationId);
  if (turn.unsearched.length === 0) {
    return null;
  }
  return (
    <p className={styles.notice}>
      {t("reporter.unsearched", { words: turn.unsearched.join(", ") })}{" "}
      {last && turn.concepts.length < 4 && (
        <button
          type="button"
          className={styles.button}
          disabled={setTerms.isPending}
          onClick={() => {
            setTerms.mutate({
              turnId: turn.id,
              concepts: [
                ...turn.concepts.map((c) => ({ name: c.name, terms: [...c.terms, ...c.added] })),
                ...turn.unsearched.slice(0, 4 - turn.concepts.length).map((word) => ({ name: word, terms: [word] })),
              ],
            });
          }}
        >
          {t("reporter.addUnsearched")}
        </button>
      )}
    </p>
  );
}

/** Questions that follow a set, in one click: the Reporter is strongest when they are chained. */
function Suggestions({ workspaceId, conversationId, turn }: { workspaceId: string; conversationId: string; turn: TurnView }) {
  const { t } = useTranslation();
  const ask = useAsk(workspaceId, conversationId);
  const sorted = turn.candidates.some((c) => c.judged !== null);
  const questions = [
    ...(sorted ? [] : [t("reporter.suggest.sort")]),
    ...(turn.language === null ? [t("reporter.suggest.dutch"), t("reporter.suggest.french")] : []),
  ];
  return (
    <p className={styles.row} style={{ flexWrap: "wrap" }}>
      <span className={styles.meta}>{t("reporter.suggest.title")}</span>
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          className={styles.chip}
          disabled={ask.isPending}
          onClick={() => {
            ask.mutate(question);
          }}
        >
          {question}
        </button>
      ))}
    </p>
  );
}

/** The set of the answer: its count opens the items; after a sort, by verdict; a large set by
 * its main themes, each a click away. */
function ItemSet({
  workspaceId,
  conversationId,
  turn,
  title,
  last,
  selected,
  onSelect,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  title: string;
  last: boolean;
  selected: string[];
  onSelect: (selected: string[]) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(last && turn.candidates.length <= SHOWN_AT_ONCE);
  const [showThemes, setShowThemes] = useState(turn.candidates.length >= THEMES_OPEN);
  const [theme, setTheme] = useState<number | null>(null);
  const [showAside, setShowAside] = useState(false);
  const picked = theme === null ? null : turn.themes[theme];
  const inTheme = picked === undefined || picked === null ? turn.candidates : turn.candidates.filter((c) => picked.items.includes(c.id));
  const sorted = inTheme.some((c) => c.judged !== null);
  const kept = sorted ? inTheme.filter((c) => c.judged?.verdict === "traite") : inTheme;
  // Set aside by the sort: out of the list, one click away (Joël, 2026-10-30).
  const aside = sorted ? inTheme.filter((c) => c.judged?.verdict === "hors_sujet") : [];
  const toCheck = sorted ? inTheme.filter((c) => !kept.includes(c) && !aside.includes(c)) : [];
  const count = (verdict: string) => inTheme.filter((c) => c.judged?.verdict === verdict).length;
  const toBriefWith = (ids: string[]) => {
    void navigate({
      to: "/redaction/nouveau",
      search: { items: ids.slice(0, BRIEF_MAX).join(","), title, angle: "" },
    });
  };
  const toBrief = (items: TurnCandidate[]) => {
    toBriefWith(items.map((c) => c.id));
  };
  const toggle = (id: string, on: boolean) => {
    onSelect(on ? [...selected, id] : selected.filter((other) => other !== id));
  };
  // After a sort, the kept ones or the whole set, when it fits in a brief: the author chooses.
  const someKept = sorted && kept.length > 0 && kept.length < inTheme.length;
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
      {turn.themes.length > 0 && !showThemes && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.chip}
            onClick={() => {
              setShowThemes(true);
            }}
          >
            {t("reporter.suggest.themes")}
          </button>
        </p>
      )}
      {showThemes && turn.themes.length > 0 && (
        <div>
          <p className={styles.meta}>{t("reporter.themes", { count: turn.candidates.length })}</p>
          <p className={styles.row} style={{ flexWrap: "wrap" }}>
            {turn.themes.map((found, index) => (
              <button
                key={found.label}
                type="button"
                className={styles.chip}
                aria-pressed={theme === index}
                style={theme === index ? { fontWeight: 600 } : undefined}
                onClick={() => {
                  setTheme(theme === index ? null : index);
                  setOpen(true);
                }}
              >
                {found.label} ({found.items.length})
              </button>
            ))}
          </p>
          <p className={styles.help}>{t("reporter.themesHelp")}</p>
        </div>
      )}
      {turn.candidates.length === 0 && (
        <p className={styles.notice}>
          {turn.concepts.length === 0 && turn.days === null ? t("reporter.noSubject") : t("reporter.emptySet")}
        </p>
      )}
      {turn.candidates.length >= SET_MAX && <p className={styles.notice}>{t("reporter.broad", { max: SET_MAX })}</p>}
      {open && <Items candidates={[...kept, ...toCheck]} selected={selected} onToggle={toggle} />}
      {open && aside.length > 0 && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.chip}
            aria-expanded={showAside}
            onClick={() => {
              setShowAside(!showAside);
            }}
          >
            {showAside ? t("reporter.hideAside") : t("reporter.showAside", { count: aside.length })}
          </button>
        </p>
      )}
      {open && showAside && <Items candidates={aside} selected={selected} onToggle={toggle} />}
      {last && turn.candidates.length > 0 && (
        <Suggestions workspaceId={workspaceId} conversationId={conversationId} turn={turn} />
      )}
      {last && !sorted && selected.length === 0 && inTheme.length > BRIEF_MAX && (
        <p className={styles.help}>{t("reporter.sortFirst", { max: BRIEF_MAX })}</p>
      )}
      {selected.length > 0 && (
        <p className={styles.row} style={{ flexWrap: "wrap" }}>
          <button
            type="button"
            className={styles.button}
            disabled={selected.length > BRIEF_MAX}
            onClick={() => {
              toBriefWith(selected);
            }}
          >
            {t("reporter.toBrief", { count: selected.length })}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              onSelect([]);
            }}
          >
            {t("reporter.unselect")}
          </button>
          {selected.length > BRIEF_MAX && <span className={styles.notice}>{t("reporter.tooMany", { max: BRIEF_MAX })}</span>}
        </p>
      )}
      {selected.length === 0 && inTheme.length > 0 && (
        <p className={styles.row} style={{ flexWrap: "wrap" }}>
          {someKept && (
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                toBrief(kept);
              }}
            >
              {kept.length > BRIEF_MAX
                ? t("reporter.toBriefKeptFirst", { count: BRIEF_MAX })
                : t("reporter.toBriefKept", { count: kept.length })}
            </button>
          )}
          {(!someKept || inTheme.length <= BRIEF_MAX) && (
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                toBrief(inTheme);
              }}
            >
              {inTheme.length > BRIEF_MAX
                ? t("reporter.toBriefFirst", { count: BRIEF_MAX })
                : someKept
                  ? aside.length > 0
                    ? t("reporter.toBriefAllAside", { count: inTheme.length })
                    : t("reporter.toBriefAll", { count: inTheme.length })
                  : t("reporter.toBrief", { count: inTheme.length })}
            </button>
          )}
        </p>
      )}
    </>
  );
}

/** « Reconstituer » (ADR-0044 §7): only when asked; the lines by date, the facets as filters; the
 * analysis apart, with its computed confidence. */
function Rebuild({
  workspaceId,
  conversationId,
  turn,
  busy,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const rebuild = useReconstitute(workspaceId, conversationId);
  const onSubject = useReconstituteSubject(workspaceId, conversationId);
  const [facet, setFacet] = useState<number | null>(null);
  const done = turn.reconstitution;
  if (done !== null && done.subjects.length > 0) {
    return (
      <section aria-label={t("reporter.rebuild.subjects")}>
        <h3>{t("reporter.rebuild.subjects")}</h3>
        <p className={styles.help}>{t("reporter.rebuild.subjectsHelp", { read: done.read, found: done.found })}</p>
        <ol>
          {done.subjects.map((subject, index) => (
            <li key={index} style={{ margin: "0.75rem 0" }}>
              <strong>{subject.title}</strong>
              <br />
              {subject.summary}
              {subject.unsupported.length > 0 && (
                <>
                  <br />
                  <span className={styles.warning}>
                    {t("reporter.rebuild.unsupported", { words: subject.unsupported.join(", ") })}
                  </span>
                </>
              )}
              <br />
              <span className={styles.meta}>
                {subject.articles.map((article, position) => (
                  <span key={article.item_id}>
                    {position > 0 && " · "}
                    <Link to="/veille/elements/$itemId" params={{ itemId: article.item_id }}>
                      {article.publisher}
                    </Link>
                  </span>
                ))}
              </span>{" "}
              <button
                type="button"
                className={styles.button}
                disabled={busy || onSubject.isPending}
                onClick={() => {
                  onSubject.mutate({ turnId: turn.id, subject: index });
                }}
              >
                {t("reporter.rebuild.oneSubject")}
              </button>
            </li>
          ))}
        </ol>
        {onSubject.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, onSubject.error)}
          </p>
        )}
      </section>
    );
  }
  if (done === null || (done.facets.length === 0 && done.errors.length > 0)) {
    return turn.candidates.length === 0 ? null : (
      <>
        {done !== null && (
          <p className={styles.warning}>{t("reporter.rebuild.failed", { error: done.errors.join("; ") })}</p>
        )}
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            disabled={busy || rebuild.isPending}
            onClick={() => {
              rebuild.mutate(turn.id);
            }}
          >
            {t("reporter.rebuild.button")}
          </button>
          <span className={styles.meta}>{t("reporter.rebuild.help")}</span>
        </p>
        {rebuild.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, rebuild.error)}
          </p>
        )}
      </>
    );
  }
  if (done.facets.length === 0) {
    return <p className={styles.notice}>{t("reporter.rebuild.nothing", { count: done.found })}</p>;
  }
  const numbered = done.lines.map((line, index) => ({ line, number: index + 1 }));
  const shown = facet === null ? numbered : numbered.filter(({ line }) => line.facet === facet);
  return (
    <section aria-label={t("reporter.rebuild.title")}>
      <div className={styles.panel}>
        <h3>{t("reporter.rebuild.inBrief")}</h3>
        {done.answer.length === 0 && done.sentences.length === 0 && (
          <p className={styles.notice}>{t("reporter.rebuild.noAnalysis")}</p>
        )}
        {done.answer.map((sentence, index) => (
          <RebuiltSentence key={index} sentence={sentence} strong={index === 0} />
        ))}
        {done.confidence !== null && (
          <p>
            <strong>{t(`reporter.rebuild.confidence.${done.confidence}`)}</strong>
            {done.reasons.length > 0 && <span className={styles.meta}> · {done.reasons.join(" ; ")}</span>}
          </p>
        )}
        <p className={styles.help}>{t("reporter.rebuild.byModel", { read: done.read, found: done.found })}</p>
      </div>
      <details>
        <summary>{t("reporter.rebuild.facts", { count: done.lines.length })}</summary>
      <p className={styles.row} style={{ flexWrap: "wrap" }}>
        {done.facets.map((one, index) => (
          <button
            key={one.name}
            type="button"
            className={styles.chip}
            title={one.question}
            aria-pressed={facet === index + 1}
            style={facet === index + 1 ? { fontWeight: 600 } : undefined}
            onClick={() => {
              setFacet(facet === index + 1 ? null : index + 1);
            }}
          >
            {one.name} ({done.lines.filter((line) => line.facet === index + 1).length})
          </button>
        ))}
      </p>
      {shown.length === 0 && <p className={styles.notice}>{t("reporter.rebuild.noLine")}</p>}
      {shown.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">{t("reporter.rebuild.line")}</th>
              <th scope="col">{t("reporter.fact.source")}</th>
              <th scope="col">{t("reporter.rebuild.information")}</th>
              <th scope="col">{t("reporter.fact.when")}</th>
              <th scope="col">{t("reporter.fact.where")}</th>
              <th scope="col">{t("reporter.fact.passage")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ line, number }) => (
              <tr key={number}>
                <td>L{number}</td>
                <td>
                  <Link to="/veille/elements/$itemId" params={{ itemId: line.item_id }}>
                    {line.publisher}
                  </Link>
                  <br />
                  <span className={styles.meta}>{formatDate(line.dated)}</span>
                </td>
                <td>{line.information}</td>
                <td>{line.when}</td>
                <td>{line.where}</td>
                <td>
                  <q>{line.passage}</q>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {done.flagged.length > 0 && (
        <details>
          <summary>{t("reporter.rebuild.flagged", { count: done.flagged.length })}</summary>
          <ul>
            {done.flagged.map((line, index) => (
              <li key={index}>
                {line.information} ({line.publisher}) · <span className={styles.warning}>{line.to_check.join(", ")}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      </details>
      {done.sentences.length > 0 && (
        <details>
          <summary>{t("reporter.rebuild.analysis")}</summary>
          {done.sentences.map((sentence, index) => (
            <RebuiltSentence key={index} sentence={sentence} />
          ))}
        </details>
      )}
      {done.errors.length > 0 && (
        <p className={styles.notice}>{t("reporter.rebuild.failed", { error: done.errors.join("; ") })}</p>
      )}
    </section>
  );
}

/** A sentence of the answer or of the analysis, with its lines and what they do not hold. */
function RebuiltSentence({ sentence, strong = false }: { sentence: SentenceView; strong?: boolean }) {
  const { t } = useTranslation();
  return (
    <p>
      {sentence.deduction && <em>{t("reporter.rebuild.deduction")} </em>}
      {strong ? <strong>{sentence.text}</strong> : sentence.text}{" "}
      <span className={styles.meta}>{sentence.lines.map((n) => `L${String(n)}`).join(" ")}</span>
      {sentence.unsupported.length > 0 && (
        <>
          <br />
          <span className={styles.warning}>
            {t("reporter.rebuild.unsupported", { words: sentence.unsupported.join(", ") })}
          </span>
        </>
      )}
    </p>
  );
}

function Items({
  candidates,
  selected,
  onToggle,
}: {
  candidates: TurnCandidate[];
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <ul style={{ listStyle: "none", padding: 0 }}>
      {candidates.map((candidate) => (
        <li key={candidate.id} style={{ margin: "0.5rem 0" }}>
          <input
            type="checkbox"
            aria-label={t("reporter.selectArticle", { title: candidate.title })}
            checked={selected.includes(candidate.id)}
            onChange={(event) => {
              onToggle(candidate.id, event.target.checked);
            }}
          />{" "}
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
function Fact({
  workspaceId,
  conversationId,
  turn,
  fact,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  fact: FactView | null;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const more = useReadMore(workspaceId, conversationId);
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
      {fact.read.length < turn.candidates.length && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            disabled={more.isPending}
            onClick={() => {
              more.mutate(turn.id);
            }}
          >
            {t("reporter.fact.more", { count: Math.min(15, turn.candidates.length - fact.read.length) })}
          </button>
          <span className={styles.meta}>
            {t("reporter.fact.left", { count: turn.candidates.length - fact.read.length })}
          </span>
        </p>
      )}
      {more.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, more.error)}
        </p>
      )}
      {fact.conclusion !== "" && fact.lines.length > 0 && (
        <p className={styles.meta}>{t("reporter.fact.conclusion", { text: fact.conclusion })}</p>
      )}
      {fact.lines.length > 0 && (
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              void navigate({
                to: "/redaction/nouveau",
                search: {
                  items: [...new Set(fact.lines.map((line) => line.item_id))].slice(0, BRIEF_MAX).join(","),
                  title: turn.question,
                  conversation: conversationId,
                  turn: turn.id,
                },
              });
            }}
          >
            {t("reporter.fact.toBrief", { count: fact.lines.length })}
          </button>
        </p>
      )}
    </>
  );
}

/** « Vérifier en lisant » (Joël, 2026-10-29): the model reads the first items of the set, as a
 * person would, says which truly answer and what is missing, and searches once more otherwise. */
function Reading({
  workspaceId,
  conversationId,
  turn,
  busy,
}: {
  workspaceId: string;
  conversationId: string;
  turn: TurnView;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const readSet = useReadSet(workspaceId, conversationId);
  const reading: ReadingView | null = turn.reading;
  if (reading === null || reading.rounds.length === 0) {
    return (
      <>
        {reading !== null && reading.errors.length > 0 && (
          <p className={styles.warning}>{t("reporter.reading.failed", { error: reading.errors.join("; ") })}</p>
        )}
        <p className={styles.row}>
          <button
            type="button"
            className={styles.button}
            disabled={busy || readSet.isPending}
            onClick={() => {
              readSet.mutate(turn.id);
            }}
          >
            {t("reporter.reading.button")}
          </button>
          <span className={styles.meta}>{t("reporter.reading.help")}</span>
        </p>
        {readSet.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, readSet.error)}
          </p>
        )}
      </>
    );
  }
  const read = reading.rounds.reduce((sum, round) => sum + round.read, 0);
  const second = reading.rounds[1];
  return (
    <section aria-label={t("reporter.reading.title")}>
      <h3>{t("reporter.reading.title")}</h3>
      <p className={styles.meta}>
        {t("reporter.reading.read", { count: read })}
        {second !== undefined &&
          ` · ${t("reporter.reading.second", {
            terms: second.concepts.map((c) => c.terms.join(", ")).join(" ET "),
            count: second.read,
          })}`}
      </p>
      {reading.coverage !== null && (
        <p>
          <strong>{t(`reporter.reading.coverage.${reading.coverage}`)}</strong>
        </p>
      )}
      {reading.missing !== "" && (
        <p className={styles.notice}>{t("reporter.reading.missing", { text: reading.missing })}</p>
      )}
      {reading.answers.length === 0 ? (
        <p className={styles.notice}>{t("reporter.reading.none")}</p>
      ) : (
        <ul>
          {reading.answers.map((answer) => (
            <li key={answer.item_id}>
              <Link to="/veille/elements/$itemId" params={{ itemId: answer.item_id }}>
                {answer.title}
              </Link>{" "}
              <span className={styles.meta}>
                {answer.publisher} · {formatDate(answer.dated)}
                {answer.round === 2 && ` · ${t("reporter.reading.fromSecond")}`}
              </span>
              {answer.reason !== "" && (
                <>
                  <br />
                  <span className={styles.meta}>{answer.reason}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className={styles.help}>{t("reporter.reading.byModel")}</p>
      {reading.errors.length > 0 && (
        <p className={styles.warning}>{t("reporter.reading.failed", { error: reading.errors.join("; ") })}</p>
      )}
    </section>
  );
}
