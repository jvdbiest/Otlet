// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Form, Input, Label, TextField } from "react-aria-components";
import { sourcesQuery, type ItemView } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import {
  FEED_PAGE_SIZE,
  feedQuery,
  type FeedFilter,
  type FeedView,
  type TriageView,
} from "../../triage.ts";
import { searchQuery, useRefreshWatch } from "../../watch.ts";
import { formatDate, textLabel, textTone } from "./labels.ts";
import { StartPanel } from "./StartPanel.tsx";
import { styles } from "./styles.ts";
import { TriageActions } from "./TriageActions.tsx";

const VIEWS: readonly FeedView[] = ["to_sort", "kept", "pinned", "dismissed", "all"];

/** The feed of the user: what is left to sort first, then what was kept, pinned or dismissed
 * (X02, F-VEI-04, F-VEI-05). */
export function ItemsPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Items workspaceId={workspaceId} />;
}

function Items({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FeedFilter>({ view: "to_sort", sourceId: null, unread: false });
  // Older pages, each starting after the last item of the previous one.
  const [pages, setPages] = useState<(string | null)[]>([null]);
  const sources = useQuery(sourcesQuery(workspaceId));
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const update = (next: Partial<FeedFilter>) => {
    setFilter((current) => ({ ...current, ...next }));
    setPages([null]);
  };

  return (
    <>
      <StartPanel workspaceId={workspaceId} />
      <RefreshButton workspaceId={workspaceId} />
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
          <div className={styles.views} role="radiogroup" aria-label={t("triage.views.label")}>
            {VIEWS.map((view) => (
              <button
                key={view}
                type="button"
                role="radio"
                aria-checked={filter.view === view}
                className={styles.viewButton}
                onClick={() => {
                  update({ view });
                }}
              >
                {t(`triage.views.${view}`)}
              </button>
            ))}
          </div>
          <div className={styles.search}>
            {sources.data !== undefined && sources.data.length > 0 && (
              <div className={styles.field}>
                <label htmlFor="source-filter">{t("watch.filter")}</label>
                <select
                  id="source-filter"
                  value={filter.sourceId ?? ""}
                  onChange={(event) => {
                    update({ sourceId: event.target.value === "" ? null : event.target.value });
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
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={filter.unread}
                onChange={(event) => {
                  update({ unread: event.target.checked });
                }}
              />{" "}
              {t("triage.unreadOnly")}
            </label>
          </div>
          {pages.map((before, index) => (
            <FeedPage
              key={before ?? "first"}
              workspaceId={workspaceId}
              filter={filter}
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

function FeedPage({
  workspaceId,
  filter,
  before,
  isLast,
  onMore,
}: {
  workspaceId: string;
  filter: FeedFilter;
  before: string | null;
  isLast: boolean;
  onMore: (before: string) => void;
}) {
  const { t } = useTranslation();
  const feed = useQuery(feedQuery(workspaceId, filter, before));
  if (feed.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (feed.data === undefined) {
    return before === null ? <p>{t("app.loading")}</p> : null;
  }
  if (feed.data.length === 0 && before === null) {
    return <p className={styles.meta}>{t(`triage.empty.${filter.view}`)}</p>;
  }
  const last = feed.data.at(-1);
  return (
    <>
      <ul className={styles.list}>
        {feed.data.map((entry) => (
          <ItemCard key={entry.item.id} workspaceId={workspaceId} item={entry.item} triage={entry.triage} />
        ))}
      </ul>
      {isLast &&
        (feed.data.length === FEED_PAGE_SIZE && last !== undefined ? (
          <p>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                onMore(last.item.id);
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

function ItemCard({
  workspaceId,
  item,
  triage,
}: {
  workspaceId: string;
  item: ItemView;
  triage?: TriageView;
}) {
  const { t } = useTranslation();
  const date = item.published_at ?? item.collected_at;
  const unread = triage?.read_at === null;
  return (
    <li className={styles.card}>
      <h2 className={unread ? styles.unread : undefined}>
        <Link to="/veille/elements/$itemId" params={{ itemId: item.id }}>
          {item.title}
        </Link>
      </h2>
      <p className={styles.meta}>
        {unread && <span className={styles.neutral}>{t("triage.unread")}</span>}{" "}
        {item.source_name ?? t("watch.manualOrigin")} · {formatDate(date)}{" "}
        <span className={styles[textTone(item.text_status)]}>{textLabel(t, item.text_status)}</span>
        {item.duplicates > 0 && <> · {t("watch.duplicates", { count: item.duplicates })}</>}
      </p>
      {item.summary !== null && <p className={styles.meta}>{item.summary.slice(0, 280)}</p>}
      {triage !== undefined && (
        <TriageActions workspaceId={workspaceId} itemId={item.id} title={item.title} triage={triage} />
      )}
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
            <ItemCard key={result.item.id} workspaceId={workspaceId} item={result.item} />
          ))}
        </ul>
      )}
    </>
  );
}

// After « Actualiser », the lists are refreshed this often, for this long.
const REFRESH_POLL_MS = 5_000;
const REFRESH_POLL_DURATION_MS = 90_000;

/** Collects every source now and matches the topics again (U02b). */
function RefreshButton({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const refresh = useRefreshWatch(workspaceId);
  const queryClient = useQueryClient();
  const [until, setUntil] = useState(0);
  useEffect(() => {
    if (until === 0) {
      return;
    }
    const timer = window.setInterval(() => {
      if (Date.now() > until) {
        window.clearInterval(timer);
        setUntil(0);
        return;
      }
      void queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
    }, REFRESH_POLL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [until, queryClient, workspaceId]);

  return (
    <div className={styles.row}>
      <Button
        className={styles.button}
        isDisabled={refresh.isPending}
        onPress={() => {
          refresh.mutate(undefined, {
            onSuccess: () => {
              setUntil(Date.now() + REFRESH_POLL_DURATION_MS);
            },
          });
        }}
      >
        {refresh.isPending ? t("watch.refreshing") : t("watch.refresh")}
      </Button>
      {refresh.data !== undefined && (
        <span role="status" className={styles.meta}>
          {t("watch.refreshed", { sources: refresh.data.sources, topics: refresh.data.topics })}
        </span>
      )}
      {refresh.error !== null && (
        <span role="alert" className={styles.error}>
          {t("errors.generic")}
        </span>
      )}
    </div>
  );
}
