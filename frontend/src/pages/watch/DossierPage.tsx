// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { dossierQuery, useSaveEntry, useStartDossier, type DossierCandidate, type DossierView } from "../../assistant.ts";
import { useWorkspaceId } from "../../session.ts";
import { MatterPanel } from "../writing/MatterPanel.tsx";
import { errorText, formatDate } from "./labels.ts";
import { styles } from "./styles.ts";

type Group = "traite" | "proche" | "hors_sujet";
const GROUPS: readonly Group[] = ["traite", "proche", "hors_sujet"];
const BRIEF_MAX = 20;

/** A dossier of the Assistant de veille (ADR-0043): the terms searched, then the items found,
 * retenus, à vérifier, écartés; the matter of the selection (A1a); the brief to prepare. */
export function DossierPage({ dossierId }: { dossierId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Dossier workspaceId={workspaceId} dossierId={dossierId} />;
}

function Dossier({ workspaceId, dossierId }: { workspaceId: string; dossierId: string }) {
  const { t } = useTranslation();
  const dossier = useQuery(dossierQuery(workspaceId, dossierId));
  if (dossier.data === undefined) {
    return dossier.error !== null ? <p role="alert">{errorText(t, dossier.error)}</p> : <p>{t("app.loading")}</p>;
  }
  // The selection starts from the verdicts once they are known: a new key, a new state.
  return <Loaded key={dossier.data.status} workspaceId={workspaceId} dossier={dossier.data} />;
}

function groupOf(candidate: DossierCandidate): Group | null {
  return candidate.judged?.verdict ?? null;
}

function Loaded({ workspaceId, dossier }: { workspaceId: string; dossier: DossierView }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>(() =>
    dossier.candidates.filter((c) => groupOf(c) === "traite").map((c) => c.id),
  );
  const [showSetAside, setShowSetAside] = useState(false);
  const done = dossier.status === "done";
  const counts = Object.fromEntries(GROUPS.map((g) => [g, dossier.candidates.filter((c) => groupOf(c) === g).length]));
  const toggle = (id: string, on: boolean) => {
    setSelected((current) => (on ? [...current, id] : current.filter((other) => other !== id)));
  };
  const chosen = selected.slice(0, BRIEF_MAX);
  return (
    <>
      <p>
        <Link to="/veille/assistant">{t("assistant.back")}</Link>
      </p>
      <h2>{dossier.subject}</h2>
      {dossier.angle !== "" && <p className={styles.meta}>{t("assistant.angleShown", { angle: dossier.angle })}</p>}
      <Terms workspaceId={workspaceId} dossier={dossier} />
      <p role="status" className={styles.meta}>
        {dossier.status === "pending"
          ? t("assistant.status.pending")
          : dossier.status === "qualifying"
            ? t("assistant.status.qualifying", { count: dossier.candidates.length })
            : t("assistant.status.done", {
                count: dossier.candidates.length,
                kept: counts.traite,
                check: counts.proche,
                aside: counts.hors_sujet,
              })}
        {dossier.model !== null && ` · ${t("assistant.model", { model: dossier.model })}`}
      </p>
      {dossier.error !== null && <p className={styles.notice}>{t("assistant.modelError", { error: dossier.error })}</p>}
      {done && dossier.candidates.length === 0 && <p className={styles.warning}>{t("assistant.nothing")}</p>}
      {!done && dossier.candidates.length > 0 && (
        <CandidateList candidates={dossier.candidates} selected={selected} onToggle={toggle} />
      )}
      {done &&
        GROUPS.map((group) => {
          const members = dossier.candidates.filter((c) => groupOf(c) === group);
          if (members.length === 0) {
            return null;
          }
          const folded = group === "hors_sujet" && !showSetAside;
          return (
            <section key={group} className={styles.panel} aria-labelledby={`group-${group}`}>
              <h3 id={`group-${group}`} className={styles.row}>
                <span>{t(`assistant.groups.${group}`, { count: members.length })}</span>
                {group === "hors_sujet" && (
                  <button
                    type="button"
                    className={styles.button}
                    aria-expanded={!folded}
                    onClick={() => {
                      setShowSetAside(!showSetAside);
                    }}
                  >
                    {folded ? t("assistant.show") : t("assistant.hide")}
                  </button>
                )}
              </h3>
              {!folded && <CandidateList candidates={members} selected={selected} onToggle={toggle} />}
            </section>
          );
        })}
      {done && selected.length > 0 && (
        <section className={styles.panel} aria-labelledby="assistant-selection">
          <h3 id="assistant-selection">{t("assistant.selection", { count: selected.length })}</h3>
          <MatterPanel workspaceId={workspaceId} itemIds={chosen} length="medium" mode="synthesis" nature="news" />
          {selected.length > BRIEF_MAX && <p className={styles.notice}>{t("assistant.tooMany", { max: BRIEF_MAX })}</p>}
          <p className={styles.row}>
            <button
              type="button"
              className={styles.primary}
              onClick={() => {
                void navigate({
                  to: "/redaction/nouveau",
                  search: { items: chosen.join(","), title: dossier.subject, angle: dossier.angle },
                });
              }}
            >
              {t("assistant.toBrief", { count: chosen.length })}
            </button>
          </p>
        </section>
      )}
    </>
  );
}

function CandidateList({
  candidates,
  selected,
  onToggle,
}: {
  candidates: DossierCandidate[];
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <ul style={{ listStyle: "none", padding: 0 }}>
      {candidates.map((candidate) => (
        <li key={candidate.id} style={{ margin: "0.6rem 0" }}>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
            <input
              type="checkbox"
              checked={selected.includes(candidate.id)}
              onChange={(event) => {
                onToggle(candidate.id, event.target.checked);
              }}
            />
            <span>
              <span className={styles.meta}>[{(candidate.language ?? "?").slice(0, 2).toUpperCase()}]</span>{" "}
              <Link to="/veille/elements/$itemId" params={{ itemId: candidate.id }}>
                {candidate.title}
              </Link>
              <br />
              <span className={styles.meta}>
                {[candidate.publisher, candidate.country, formatDate(candidate.dated)].filter(Boolean).join(" · ")}
              </span>
              {candidate.judged !== null && (
                <>
                  <br />
                  <span className={styles.help}>
                    {candidate.judged.by_model
                      ? t("assistant.reason", { reason: candidate.judged.reason })
                      : candidate.judged.reason}
                  </span>
                </>
              )}
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}

/** The terms searched, as the author can check them: theirs, and those the glossary added. */
function Terms({ workspaceId, dossier }: { workspaceId: string; dossier: DossierView }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const start = useStartDossier(workspaceId);
  const save = useSaveEntry(workspaceId);
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState(() => dossier.concepts.map((c) => [...c.terms, ...c.added].join(", ")));
  const [kept, setKept] = useState<number[]>([]);
  const failed = start.error ?? save.error;
  if (dossier.concepts.length === 0) {
    return null;
  }
  return (
    <section className={styles.panel} aria-labelledby="assistant-terms">
      <h3 id="assistant-terms">{t("assistant.terms.title")}</h3>
      {dossier.concepts.map((concept, index) => (
        <div key={concept.name + String(index)} className={styles.row} style={{ flexWrap: "wrap" }}>
          {index > 0 && <strong>{t("assistant.terms.and")}</strong>}
          {editing ? (
            <input
              aria-label={t("assistant.terms.concept", { name: concept.name })}
              style={{ flex: "1 1 30rem" }}
              value={drafts[index] ?? ""}
              onChange={(event) => {
                setDrafts(drafts.map((d, n) => (n === index ? event.target.value : d)));
              }}
            />
          ) : (
            <>
              {concept.terms.map((term) => (
                <span key={term} className={styles.chip}>
                  {term}
                </span>
              ))}
              {concept.added.map((term) => (
                <span key={term} className={styles.chip} title={t("assistant.terms.fromGlossary")}>
                  {term} ·{" "}
                  <small>{t("assistant.terms.glossary")}</small>
                </span>
              ))}
              {concept.terms.length > 1 && !kept.includes(index) && (
                <button
                  type="button"
                  className={styles.button}
                  disabled={save.isPending}
                  onClick={() => {
                    save.mutate(
                      { entryId: null, terms: [...concept.terms] },
                      {
                        onSuccess: () => {
                          setKept([...kept, index]);
                        },
                      },
                    );
                  }}
                >
                  {t("assistant.terms.keep")}
                </button>
              )}
              {kept.includes(index) && <span className={styles.meta}>{t("assistant.terms.kept")}</span>}
            </>
          )}
        </div>
      ))}
      <p className={styles.help}>{t("assistant.terms.help")}</p>
      <p className={styles.row}>
        {editing ? (
          <button
            type="button"
            className={styles.primary}
            disabled={start.isPending}
            onClick={() => {
              start.mutate(
                {
                  subject: dossier.subject,
                  angle: dossier.angle,
                  days: dossier.days,
                  concepts: dossier.concepts.map((c, n) => ({
                    name: c.name,
                    terms: (drafts[n] ?? "").split(",").map((term) => term.trim()).filter((term) => term !== ""),
                  })),
                },
                {
                  onSuccess: (next) => {
                    void navigate({ to: "/veille/assistant/$dossierId", params: { dossierId: next.id } });
                  },
                },
              );
            }}
          >
            {t("assistant.terms.rerun")}
          </button>
        ) : (
          <button
            type="button"
            className={styles.button}
            disabled={dossier.status !== "done"}
            onClick={() => {
              setEditing(true);
            }}
          >
            {t("assistant.terms.edit")}
          </button>
        )}
      </p>
      {failed !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, failed)}
        </p>
      )}
    </section>
  );
}
