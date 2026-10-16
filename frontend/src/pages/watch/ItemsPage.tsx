// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Form, Input, Label, TextField } from "react-aria-components";
import { itemsQuery, PAGE_SIZE, sourcesQuery, type ItemView } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import { searchQuery } from "../../watch.ts";
import { formatDate, textLabel, textTone } from "./labels.ts";
import { emptyStyles, styles } from "./styles.ts";

/** The latest items of every source, newest first (U01). */
export function ItemsPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Items workspaceId={workspaceId} />;
}

function Items({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const [sourceId, setSourceId] = useState<string | null>(null);
  // Older pages, each starting before the last item of the previous one.
  const [pages, setPages] = useState<(string | null)[]>([null]);
  const sources = useQuery(sourcesQuery(workspaceId));
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");

  return (
    <>
      <SearchBox
        draft={draft}
        onDraft={setDraft}
        active={query !== ""}
        onSearch={() => {
          setQuery(draft.trim());
        }}
        onClear={() => {
          setDraft("");
          setQuery("");
        }}
      />
      {query !== "" ? (
        <SearchResults workspaceId={workspaceId} query={query} />
      ) : (
        <>
      {sources.data !== undefined && sources.data.length > 0 && (
        <div className={`${styles.field} ${styles.filter}`}>
          <label htmlFor="source-filter">{t("watch.filter")}</label>
          <select
            id="source-filter"
            value={sourceId ?? ""}
            onChange={(event) => {
              setSourceId(event.target.value === "" ? null : event.target.value);
              setPages([null]);
            }}
          >
            <option value="">{t("watch.allSources")}</option>
            {sources.data.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {pages.map((before, index) => (
        <ItemsPageOf
          key={before ?? "first"}
          workspaceId={workspaceId}
          sourceId={sourceId}
          before={before}
          isLast={index === pages.length - 1}
          onMore={(next) => {
            setPages((current) => [...current, next]);
          }}
        />
      ))}
        </>
      )}
    </>
  );
}

function ItemsPageOf({
  workspaceId,
  sourceId,
  before,
  isLast,
  onMore,
}: {
  workspaceId: string;
  sourceId: string | null;
  before: string | null;
  isLast: boolean;
  onMore: (before: string) => void;
}) {
  const { t } = useTranslation();
  const items = useQuery(itemsQuery(workspaceId, sourceId, before));
  if (items.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (items.data === undefined) {
    return before === null ? <p>{t("app.loading")}</p> : null;
  }
  if (items.data.length === 0 && before === null) {
    return (
      <div className={emptyStyles.empty}>
        <p className={emptyStyles.headline}>{t("pages.watch.empty")}</p>
        <p className={emptyStyles.next}>{t("pages.watch.next")}</p>
        <p>
          <Link to="/veille/sources">{t("watch.addSource")}</Link>
        </p>
      </div>
    );
  }
  const last = items.data.at(-1);
  return (
    <>
      <ul className={styles.list}>
        {items.data.map((item) => (
          <ItemCard key={item.id} item={item} />
        ))}
      </ul>
      {isLast &&
        (items.data.length === PAGE_SIZE && last !== undefined ? (
          <p>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                onMore(last.id);
              }}
            >
              {t("watch.more")}
            </button>
          </p>
        ) : (
          before !== null && <p className={styles.meta}>{t("watch.end")}</p>
        ))}
    </>
  );
}

function ItemCard({ item }: { item: ItemView }) {
  const { t } = useTranslation();
  const date = item.published_at ?? item.collected_at;
  return (
    <li className={styles.card}>
      <h2>
        <Link to="/veille/elements/$itemId" params={{ itemId: item.id }}>
          {item.title}
        </Link>
      </h2>
      <p className={styles.meta}>
        {item.source_name ?? t("watch.manualOrigin")} · {formatDate(date)}{" "}
        <span className={styles[textTone(item.text_status)]}>{textLabel(t, item.text_status)}</span>
        {item.duplicates > 0 && <> · {t("watch.duplicates", { count: item.duplicates })}</>}
      </p>
      {item.summary !== null && <p className={styles.meta}>{item.summary.slice(0, 280)}</p>}
    </li>
  );
}


function SearchBox({
  draft,
  onDraft,
  active,
  onSearch,
  onClear,
}: {
  draft: string;
  onDraft: (value: string) => void;
  active: boolean;
  onSearch: () => void;
  onClear: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Form
      role="search"
      className={styles.search}
      onSubmit={(event) => {
        event.preventDefault();
        onSearch();
      }}
    >
      <TextField className={styles.field} value={draft} onChange={onDraft} maxLength={200} type="search">
        <Label>{t("watch.search.label")}</Label>
        <Input />
      </TextField>
      <Button type="submit" className={styles.primary} isDisabled={draft.trim() === ""}>
        {t("watch.search.submit")}
      </Button>
      {active && (
        <Button className={styles.button} onPress={onClear}>
          {t("watch.search.clear")}
        </Button>
      )}
    </Form>
  );
}

/** Results of a full-text search, best match first (F-VEI-09, ADR-0021). */
function SearchResults({ workspaceId, query }: { workspaceId: string; query: string }) {
  const { t } = useTranslation();
  const found = useQuery(searchQuery(workspaceId, query));
  if (found.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (found.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  return (
    <>
      <p role="status">{t("watch.search.results", { count: found.data.length, q: query })}</p>
      {found.data.length > 0 && (
        <ul className={styles.list}>
          {found.data.map((result) => (
            <ItemCard key={result.item.id} item={result.item} />
          ))}
        </ul>
      )}
    </>
  );
}
