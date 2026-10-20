// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { workspacesQuery } from "../../session.ts";
import {
  libraryQuery,
  libraryTagsQuery,
  libraryTopicsQuery,
  exportSelection,
  useCreateArticle,
  useLibraryAction,
  type ExportKind,
  type LibraryAction,
  type LibraryEntryView,
} from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

type Grouping = "none" | "date";

/** « Nouvel article »: written by hand, without a brief, in the Library at once (Joël,
 * 2026-10-20); its page opens on the editor's empty page. */
function NewArticle({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const create = useCreateArticle(workspaceId);
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  return (
    <details className={styles.panel}>
      <summary>{t("library.new")}</summary>
      <form
        className={styles.row}
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(title, {
            onSuccess: (made) => {
              void navigate({ to: "/bibliotheque/articles/$articleId", params: { articleId: made.id } });
            },
          });
        }}
      >
        <label htmlFor="library-new-title">{t("library.newTitle")}</label>
        <input
          id="library-new-title"
          required
          maxLength={200}
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
        <button type="submit" className={styles.primary} disabled={create.isPending || title.trim() === ""}>
          {t("library.create")}
        </button>
        {create.error !== null && (
          <span role="alert" className={styles.error}>
            {errorText(t, create.error)}
          </span>
        )}
      </form>
    </details>
  );
}

const FORMATS: readonly ExportKind[] = ["pdf", "docx", "html", "md", "txt"];

/** The selection of the Library and its actions (Joël, 2026-10-20). Deleting is for good and
 * takes archived articles only: archive first, then delete. Export and duplication take the
 * validated version, else the latest. */
function SelectionBar({
  workspaceId,
  visible,
  selected,
  onSelect,
}: {
  workspaceId: string;
  visible: LibraryEntryView[];
  selected: string[];
  onSelect: (ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const act = useLibraryAction(workspaceId);
  const [done, setDone] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [failed, setFailed] = useState(false);
  const all = useRef<HTMLInputElement>(null);
  const chosen = visible.filter((entry) => selected.includes(entry.id));
  const allSelected = visible.length > 0 && chosen.length === visible.length;
  useEffect(() => {
    if (all.current !== null) {
      all.current.indeterminate = chosen.length > 0 && !allSelected;
    }
  }, [chosen.length, allSelected]);
  if (visible.length === 0) {
    return done === null ? null : (
      <p className={styles.meta} role="status">
        {done}
      </p>
    );
  }
  const ids = chosen.map((entry) => entry.id);
  const archivedCount = chosen.filter((entry) => entry.status === "archive").length;
  const busy = act.isPending || exporting;
  const run = (action: LibraryAction, articleIds: string[]) => {
    setFailed(false);
    act.mutate(
      { action, articleIds },
      {
        onSuccess: (outcome) => {
          const message = t(`library.selection.done.${action}`, { count: outcome.done.length });
          setDone(
            outcome.failed.length === 0
              ? message
              : `${message} ${t("library.selection.failed", { count: outcome.failed.length })}`,
          );
          setConfirming(false);
          onSelect([]);
        },
      },
    );
  };
  return (
    <div className={styles.bulkBar} role="region" aria-label={t("library.selection.label")}>
      <label className={styles.check}>
        <input
          ref={all}
          type="checkbox"
          checked={allSelected}
          onChange={(event) => {
            onSelect(event.target.checked ? visible.map((entry) => entry.id) : []);
            setDone(null);
            setConfirming(false);
          }}
        />{" "}
        {t("library.selection.all")}
      </label>
      <span className={styles.meta} aria-live="polite">
        {chosen.length > 0 ? t("library.selection.selected", { count: chosen.length }) : done}
      </span>
      {chosen.length > 0 && !confirming && (
        <div className={styles.row}>
          <button
            type="button"
            className={styles.button}
            disabled={chosen.length !== 1}
            title={chosen.length !== 1 ? t("library.selection.editOne") : undefined}
            onClick={() => {
              void navigate({ to: "/bibliotheque/articles/$articleId", params: { articleId: ids[0] ?? "" } });
            }}
          >
            {t("library.selection.edit")}
          </button>
          <button
            type="button"
            className={styles.button}
            disabled={busy}
            onClick={() => {
              run("duplicate", ids);
            }}
          >
            {t("library.selection.duplicate")}
          </button>
          <select
            aria-label={t("library.selection.export")}
            className={styles.button}
            value=""
            disabled={busy}
            onChange={(event) => {
              const kind = FORMATS.find((format) => format === event.target.value);
              if (kind === undefined) {
                return;
              }
              setExporting(true);
              setFailed(false);
              exportSelection(workspaceId, ids, kind)
                .then((blob) => {
                  const link = document.createElement("a");
                  link.href = URL.createObjectURL(blob);
                  link.download = `articles-${kind}.zip`;
                  link.click();
                  window.setTimeout(() => {
                    URL.revokeObjectURL(link.href);
                  }, 60_000);
                })
                .catch(() => {
                  setFailed(true);
                })
                .finally(() => {
                  setExporting(false);
                });
            }}
          >
            <option value="">{t("library.selection.export")}</option>
            {FORMATS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`draft.formats.${kind}`)}
              </option>
            ))}
          </select>
          {archivedCount < chosen.length && (
            <button
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => {
                run("archive", ids);
              }}
            >
              {t("library.selection.archive")}
            </button>
          )}
          {archivedCount > 0 && (
            <button
              type="button"
              className={styles.button}
              disabled={busy}
              onClick={() => {
                run("unarchive", ids);
              }}
            >
              {t("library.selection.unarchive")}
            </button>
          )}
          <button
            type="button"
            className={styles.button}
            disabled={busy || archivedCount === 0}
            title={archivedCount === 0 ? t("library.selection.deleteArchivedOnly") : undefined}
            onClick={() => {
              setConfirming(true);
            }}
          >
            {t("library.selection.delete")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              onSelect([]);
            }}
          >
            {t("library.selection.none")}
          </button>
        </div>
      )}
      {confirming && (
        <div className={styles.row} role="alertdialog" aria-label={t("library.selection.delete")}>
          <span>
            {t("library.selection.confirmDelete", { count: archivedCount })}
            {archivedCount < chosen.length &&
              ` ${t("library.selection.notArchivedKept", { count: chosen.length - archivedCount })}`}
          </span>
          <button
            type="button"
            className={styles.primary}
            disabled={busy}
            onClick={() => {
              run(
                "delete",
                chosen.filter((entry) => entry.status === "archive").map((entry) => entry.id),
              );
            }}
          >
            {t("library.selection.deleteForGood")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setConfirming(false);
            }}
          >
            {t("library.selection.cancel")}
          </button>
        </div>
      )}
      {(act.error !== null || failed) && (
        <span role="alert" className={styles.error}>
          {t("errors.generic")}
        </span>
      )}
    </div>
  );
}

const DAY = 864e5;
const MONTH = new Intl.DateTimeFormat("fr-BE", { month: "long", year: "numeric" });

/** The group of a date (Joël, 2026-10-18): today, this week, this month, then each month of this
 * year, then each year. */
function period(value: string, now: Date, t: (key: "library.today" | "library.thisWeek" | "library.thisMonth") => string): string {
  const date = new Date(value);
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfWeek = startOfDay - ((now.getDay() + 6) % 7) * DAY;
  if (date.getTime() >= startOfDay) {
    return t("library.today");
  }
  if (date.getTime() >= startOfWeek) {
    return t("library.thisWeek");
  }
  if (date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()) {
    return t("library.thisMonth");
  }
  if (date.getFullYear() === now.getFullYear()) {
    const month = MONTH.format(date);
    return month.charAt(0).toUpperCase() + month.slice(1);
  }
  return String(date.getFullYear());
}

function Excerpt({ text }: { text: string }) {
  // The words searched for come between « and ».
  return (
    <p className={styles.meta}>
      {text.split(/(«[^»]*»)/).map((part, index) =>
        part.startsWith("«") && part.endsWith("»") ? <mark key={index}>{part.slice(1, -1)}</mark> : <span key={index}>{part}</span>,
      )}
    </p>
  );
}

function Entry({
  entry,
  selected,
  onToggle,
}: {
  entry: LibraryEntryView;
  selected: boolean;
  onToggle: (on: boolean) => void;
}) {
  const { t } = useTranslation();
  const ahead = entry.validated_version !== null && entry.current_version > entry.validated_version;
  return (
    <li className={selected ? `${styles.card} ${styles.selected}` : styles.card}>
      <p className={styles.cardHead}>
        <input
          type="checkbox"
          className={styles.select}
          checked={selected}
          aria-label={t("library.selection.select", { title: entry.title })}
          onChange={(event) => {
            onToggle(event.target.checked);
          }}
        />
        <Link to="/bibliotheque/articles/$articleId" params={{ articleId: entry.id }}>
          <strong>{entry.title}</strong>
        </Link>
        <span className={styles.badge}>{t(`library.status.${entry.status}`)}</span>
        {ahead && <span className={styles.badge}>{t("library.ahead", { current: entry.current_version })}</span>}
      </p>
      <p className={styles.meta}>
        {t("library.entryMeta", {
          validated: entry.validated_version ?? 0,
          date: formatDate(entry.updated_at),
        })}
        {entry.tags.length > 0 && ` · ${entry.tags.join(", ")}`}
      </p>
      {entry.topics.length > 0 && (
        <p className={styles.chips}>
          {entry.topics.map((topic) => (
            <span key={topic.id} className={styles.chip}>
              {topic.name}
            </span>
          ))}
        </p>
      )}
      {entry.excerpt && <Excerpt text={entry.excerpt} />}
    </li>
  );
}

/** The Library (X04, ADR-0037): the validated articles, searched, filtered, grouped. */
export function LibraryPage() {
  const { t } = useTranslation();
  const workspaces = useQuery(workspacesQuery);
  const workspaceId = workspaces.data?.[0]?.id ?? "";
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState("");
  const [archived, setArchived] = useState(false);
  const [tag, setTag] = useState("");
  const [topic, setTopic] = useState("");
  const [grouping, setGrouping] = useState<Grouping>("date");
  const [selected, setSelected] = useState<string[]>([]);
  const entries = useQuery({ ...libraryQuery(workspaceId, query, archived, tag, topic), enabled: workspaceId !== "" });
  const tags = useQuery({ ...libraryTagsQuery(workspaceId), enabled: workspaceId !== "" });
  const topics = useQuery({ ...libraryTopicsQuery(workspaceId), enabled: workspaceId !== "" });
  const now = new Date();
  const groups: [string, LibraryEntryView[]][] = [];
  for (const entry of entries.data ?? []) {
    const name = grouping === "date" ? period(entry.updated_at, now, t) : "";
    const last = groups.at(-1);
    if (last?.[0] === name) {
      last[1].push(entry);
    } else {
      groups.push([name, [entry]]);
    }
  }
  return (
    <section>
      <h1>{t("library.title")}</h1>
      <NewArticle workspaceId={workspaceId} />
      <p className={styles.help}>{t("library.help")}</p>
      <form
        className={styles.filter}
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(typed.trim());
        }}
      >
        <p className={styles.row}>
          <input
            type="search"
            aria-label={t("library.search")}
            placeholder={t("library.search")}
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
              if (event.target.value === "") {
                setQuery("");
              }
            }}
          />
          <button type="submit" className={styles.button}>
            {t("library.searchButton")}
          </button>
          <select
            aria-label={t("library.tag")}
            value={tag}
            onChange={(event) => {
              setTag(event.target.value);
            }}
          >
            <option value="">{t("library.allTags")}</option>
            {(tags.data ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          {(topics.data ?? []).length > 0 && (
            <select
              aria-label={t("library.topic")}
              value={topic}
              onChange={(event) => {
                setTopic(event.target.value);
              }}
            >
              <option value="">{t("library.allTopics")}</option>
              {(topics.data ?? []).map((found) => (
                <option key={found.id} value={found.id}>
                  {found.name}
                </option>
              ))}
            </select>
          )}
          <select
            aria-label={t("library.groupBy")}
            value={grouping}
            onChange={(event) => {
              setGrouping(event.target.value === "none" ? "none" : "date");
            }}
          >
            <option value="date">{t("library.groupDate")}</option>
            <option value="none">{t("library.groupNone")}</option>
          </select>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={archived}
              onChange={(event) => {
                setArchived(event.target.checked);
              }}
            />
            {t("library.archived")}
          </label>
        </p>
      </form>
      <SelectionBar
        workspaceId={workspaceId}
        visible={entries.data ?? []}
        selected={selected}
        onSelect={setSelected}
      />
      {entries.data?.length === 0 && (
        <p className={styles.help}>{query || tag || topic ? t("library.noMatch") : t("library.empty")}</p>
      )}
      {groups.map(([name, members]) => (
        <section key={name || "all"} className={styles.group} aria-label={name || t("library.title")}>
          {name && <h2>{name}</h2>}
          <ul className={styles.list}>
            {members.map((entry) => (
              <Entry
                key={entry.id}
                entry={entry}
                selected={selected.includes(entry.id)}
                onToggle={(on) => {
                  setSelected((before) => (on ? [...before, entry.id] : before.filter((id) => id !== entry.id)));
                }}
              />
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}
