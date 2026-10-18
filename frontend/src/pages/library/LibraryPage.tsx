// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { workspacesQuery } from "../../session.ts";
import { libraryQuery, libraryTagsQuery, type LibraryEntryView } from "../../writing.ts";
import { formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

type Grouping = "none" | "date";

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

function Entry({ entry }: { entry: LibraryEntryView }) {
  const { t } = useTranslation();
  const ahead = entry.validated_version !== null && entry.current_version > entry.validated_version;
  return (
    <li className={styles.card}>
      <p className={styles.cardHead}>
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
  const [grouping, setGrouping] = useState<Grouping>("date");
  const entries = useQuery({ ...libraryQuery(workspaceId, query, archived, tag), enabled: workspaceId !== "" });
  const tags = useQuery({ ...libraryTagsQuery(workspaceId), enabled: workspaceId !== "" });
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
      {entries.data?.length === 0 && (
        <p className={styles.help}>{query || tag ? t("library.noMatch") : t("library.empty")}</p>
      )}
      {groups.map(([name, members]) => (
        <section key={name || "all"} className={styles.group} aria-label={name || t("library.title")}>
          {name && <h2>{name}</h2>}
          <ul className={styles.list}>
            {members.map((entry) => (
              <Entry key={entry.id} entry={entry} />
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}
