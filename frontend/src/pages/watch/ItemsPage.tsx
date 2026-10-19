// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Button, Form, Input, Label, TextField } from "react-aria-components";
import { sourcesQuery, type ItemView } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import {
  ANY_TIME,
  FEED_PAGE_SIZE,
  feedQuery,
  groupsQuery,
  type FeedFilter,
  type FeedSort,
  type FeedView,
  type GroupBy,
  type Period,
  type TopicTagView,
  type TriageView,
} from "../../triage.ts";
import { searchQuery, useRefreshWatch, type FoundItemView } from "../../watch.ts";
import { formatDate, textLabel, textTone } from "./labels.ts";
import { BulkBar } from "./BulkBar.tsx";
import { PeriodFilter } from "./PeriodFilter.tsx";
import { StartPanel } from "./StartPanel.tsx";
import { styles } from "./styles.ts";
import { TopicBadge } from "./TopicBadge.tsx";
import { TopicMenu } from "./TopicMenu.tsx";
import { TriageActions } from "./TriageActions.tsx";

const VIEWS: readonly FeedView[] = ["to_sort", "kept", "writing", "pinned", "archived", "dismissed", "all"];
const SORTS: readonly FeedSort[] = ["date", "score", "topic", "source"];
const GROUPS: readonly GroupBy[] = ["topic", "source"];

// The sort and the grouping are remembered in this browser, for the next visit.
const SORT_KEY = "otlet.feed.sort";
const GROUP_KEY = "otlet.feed.group";

function remembered<T extends string>(key: string, among: readonly T[]): T | null {
  try {
    const value = window.localStorage.getItem(key);
    return among.find((choice) => choice === value) ?? null;
  } catch {
    return null;
  }
}

function remember(key: string, value: string | null) {
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Without storage, the choice lasts until the page is left.
  }
}

/** The feed of the user: what is left to sort first, then what was kept, pinned or dismissed
 * (X02, F-VEI-04, F-VEI-05). */
export function ItemsPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Items workspaceId={workspaceId} />;
}

function Items({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<FeedFilter>({
    view: "to_sort",
    sourceId: null,
    unread: false,
    topicIds: [],
    allTopics: false,
    period: ANY_TIME,
    sort: remembered(SORT_KEY, SORTS) ?? "date",
    group: null,
  });
  const [groupBy, setGroupBy] = useState<GroupBy | null>(() => remembered(GROUP_KEY, GROUPS));
  const sources = useQuery(sourcesQuery(workspaceId));
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  // The selection of the bulk actions, and the items each page or the search shows.
  const [selected, setSelected] = useState<string[]>([]);
  const [loaded, setLoaded] = useState<Record<string, string[]>>({});
  const visible = Object.values(loaded).flat();
  const report = useCallback((key: string, ids: string[]) => {
    setLoaded((current) => (current[key]?.join() === ids.join() ? current : { ...current, [key]: ids }));
  }, []);
  const toggle = (id: string, on: boolean) => {
    setSelected((current) => (on ? [...current, id] : current.filter((other) => other !== id)));
  };
  const reset = () => {
    setSelected([]);
    setLoaded({});
  };
  const update = (next: Partial<FeedFilter>) => {
    setFilter((current) => ({ ...current, ...next }));
    reset();
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
          reset();
        }}
        onClear={() => {
          setDraft("");
          setQuery("");
          reset();
        }}
      />
      <TopicMenu
        workspaceId={workspaceId}
        topicIds={filter.topicIds}
        allTopics={filter.allTopics}
        onChange={(topicIds, allTopics) => {
          update({ topicIds, allTopics });
        }}
      />
      <PeriodFilter
        onChange={(period) => {
          update({ period });
        }}
      />
      <DisplayMenu
        sort={filter.sort}
        groupBy={groupBy}
        searching={query !== ""}
        onSort={(sort) => {
          remember(SORT_KEY, sort);
          update({ sort });
        }}
        onGroup={(next) => {
          remember(GROUP_KEY, next);
          setGroupBy(next);
          reset();
        }}
      />
      <BulkBar workspaceId={workspaceId} visible={visible} selected={selected} onSelect={setSelected} />
      {query !== "" ? (
        <SearchResults
          workspaceId={workspaceId}
          query={query}
          topicIds={filter.topicIds}
          allTopics={filter.allTopics}
          period={filter.period}
          groupBy={groupBy}
          selected={selected}
          onToggle={toggle}
          onLoaded={report}
        />
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
          {groupBy === null ? (
            <FeedPages
              key={JSON.stringify(filter)}
              workspaceId={workspaceId}
              filter={filter}
              prefix=""
              selected={selected}
              onToggle={toggle}
              onLoaded={report}
            />
          ) : (
            <FeedGroups
              workspaceId={workspaceId}
              filter={filter}
              by={groupBy}
              selected={selected}
              onToggle={toggle}
              onLoaded={report}
            />
          )}
        </>
      )}
    </>
  );
}

/** Trier par and Grouper par (U03): how the feed is shown, whatever the filters. During a
 * search, the order stays the relevance; the grouping still applies. */
function DisplayMenu({
  sort,
  groupBy,
  searching,
  onSort,
  onGroup,
}: {
  sort: FeedSort;
  groupBy: GroupBy | null;
  searching: boolean;
  onSort: (sort: FeedSort) => void;
  onGroup: (groupBy: GroupBy | null) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className={styles.search}>
      {!searching && (
        <div className={styles.field}>
          <label htmlFor="feed-sort">{t("triage.display.sort")}</label>
          <select
            id="feed-sort"
            value={sort}
            onChange={(event) => {
              onSort(SORTS.find((choice) => choice === event.target.value) ?? "date");
            }}
          >
            {SORTS.map((choice) => (
              <option key={choice} value={choice}>
                {t(`triage.display.sorts.${choice}`)}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className={styles.field}>
        <label htmlFor="feed-group">{t("triage.display.group")}</label>
        <select
          id="feed-group"
          value={groupBy ?? ""}
          onChange={(event) => {
            onGroup(GROUPS.find((choice) => choice === event.target.value) ?? null);
          }}
        >
          <option value="">{t("triage.display.groups.none")}</option>
          {GROUPS.map((choice) => (
            <option key={choice} value={choice}>
              {t(`triage.display.groups.${choice}`)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function groupName(t: TFunction, by: GroupBy, name: string | null): string {
  if (name !== null && name !== "") {
    return name;
  }
  return by === "topic" ? t("triage.display.noTopic") : t("triage.display.manual");
}

/** The groups of the feed, each folded or not, with how many items the filters keep in it. */
function FeedGroups({
  workspaceId,
  filter,
  by,
  selected,
  onToggle,
  onLoaded,
}: {
  workspaceId: string;
  filter: FeedFilter;
  by: GroupBy;
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
  onLoaded: (key: string, ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const groups = useQuery(groupsQuery(workspaceId, filter, by));
  const [folded, setFolded] = useState<string[]>([]);
  if (groups.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (groups.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  if (groups.data.length === 0) {
    return <p className={styles.meta}>{t(`triage.empty.${filter.view}`)}</p>;
  }
  return groups.data.map((group) => {
    const id = group.key ?? "none";
    const open = !folded.includes(id);
    const inGroup: FeedFilter = { ...filter, group: { by, key: group.key } };
    return (
      <details
        key={id}
        open={open}
        className={styles.group}
        onToggle={(event) => {
          const isOpen = event.currentTarget.open;
          setFolded((current) => (isOpen ? current.filter((other) => other !== id) : [...current, id]));
        }}
      >
        <summary>{t("triage.display.heading", { name: groupName(t, by, group.name), count: group.count })}</summary>
        {open && (
          <FeedPages
            key={JSON.stringify(inGroup)}
            workspaceId={workspaceId}
            filter={inGroup}
            prefix={`${id}:`}
            selected={selected}
            onToggle={onToggle}
            onLoaded={onLoaded}
          />
        )}
      </details>
    );
  });
}

/** The pages of the feed, each starting after the last item of the previous one. */
function FeedPages({
  workspaceId,
  filter,
  prefix,
  selected,
  onToggle,
  onLoaded,
}: {
  workspaceId: string;
  filter: FeedFilter;
  prefix: string;
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
  onLoaded: (key: string, ids: string[]) => void;
}) {
  const [pages, setPages] = useState<(string | null)[]>([null]);
  return pages.map((before, index) => (
    <FeedPage
      key={before ?? "first"}
      workspaceId={workspaceId}
      filter={filter}
      before={before}
      loadedKey={`${prefix}${before ?? "first"}`}
      isLast={index === pages.length - 1}
      onMore={(next) => {
        setPages((current) => [...current, next]);
      }}
      selected={selected}
      onToggle={onToggle}
      onLoaded={onLoaded}
    />
  ));
}

function FeedPage({
  workspaceId,
  filter,
  before,
  loadedKey,
  isLast,
  onMore,
  selected,
  onToggle,
  onLoaded,
}: {
  workspaceId: string;
  filter: FeedFilter;
  before: string | null;
  loadedKey: string;
  isLast: boolean;
  onMore: (before: string) => void;
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
  onLoaded: (key: string, ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const feed = useQuery(feedQuery(workspaceId, filter, before));
  useEffect(() => {
    if (feed.data !== undefined) {
      onLoaded(loadedKey, feed.data.map((entry) => entry.item.id));
    }
  }, [feed.data, loadedKey, onLoaded]);
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
          <ItemCard
            key={entry.item.id}
            workspaceId={workspaceId}
            item={entry.item}
            triage={entry.triage}
            topics={entry.topics}
            chosenTopics={filter.topicIds}
            selected={selected.includes(entry.item.id)}
            onToggle={(on) => {
              onToggle(entry.item.id, on);
            }}
          />
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
  topics,
  chosenTopics,
  selected,
  onToggle,
}: {
  workspaceId: string;
  item: ItemView;
  triage?: TriageView;
  topics: TopicTagView[];
  chosenTopics: string[];
  selected: boolean;
  onToggle: (on: boolean) => void;
}) {
  const { t } = useTranslation();
  const date = item.published_at ?? item.collected_at;
  const unread = triage?.read_at === null;
  return (
    <li className={selected ? `${styles.card} ${styles.selected}` : styles.card}>
      <div className={styles.cardHead}>
        <input
          type="checkbox"
          className={styles.select}
          checked={selected}
          aria-label={t("triage.bulk.select", { title: item.title })}
          onChange={(event) => {
            onToggle(event.target.checked);
          }}
        />
        <TopicBadge topics={topics} chosen={chosenTopics} />
      </div>
      <h2 className={unread ? styles.unread : undefined}>
        <Link to="/veille/elements/$itemId" params={{ itemId: item.id }}>
          {item.title}
        </Link>{" "}
        <span className={styles.meta}>({t("watch.words", { count: item.words })})</span>
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
function SearchResults({
  workspaceId,
  query,
  topicIds,
  allTopics,
  period,
  groupBy,
  selected,
  onToggle,
  onLoaded,
}: {
  workspaceId: string;
  query: string;
  topicIds: string[];
  allTopics: boolean;
  period: Period;
  groupBy: GroupBy | null;
  selected: string[];
  onToggle: (id: string, on: boolean) => void;
  onLoaded: (key: string, ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const found = useQuery(searchQuery(workspaceId, query, { topicIds, allTopics, period }));
  useEffect(() => {
    if (found.data !== undefined) {
      onLoaded("search", found.data.map((result) => result.item.id));
    }
  }, [found.data, onLoaded]);
  if (found.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (found.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  const list = (results: FoundItemView[]) => (
    <ul className={styles.list}>
      {results.map((result) => (
        <ItemCard
          key={result.item.id}
          workspaceId={workspaceId}
          item={result.item}
          triage={result.triage}
          topics={result.topics}
          chosenTopics={topicIds}
          selected={selected.includes(result.item.id)}
          onToggle={(on) => {
            onToggle(result.item.id, on);
          }}
        />
      ))}
    </ul>
  );
  return (
    <>
      <p role="status">{t("watch.search.results", { count: found.data.length, q: query })}</p>
      {found.data.length > 0 &&
        (groupBy === null
          ? list(found.data)
          : searchGroups(found.data, groupBy).map((group) => (
              <details key={group.key ?? "none"} open className={styles.group}>
                <summary>
                  {t("triage.display.heading", {
                    name: groupName(t, groupBy, group.name),
                    count: group.results.length,
                  })}
                </summary>
                {list(group.results)}
              </details>
            )))}
    </>
  );
}

/** The results of a search in groups, as the feed groups its items. A search shows its best
 * matches only: the groups count the results shown, and the best match stays first in each. */
function searchGroups(results: FoundItemView[], by: GroupBy) {
  const groups = new Map<string, { key: string | null; name: string | null; results: FoundItemView[] }>();
  for (const result of results) {
    const main = result.topics[0];
    const key = by === "topic" ? (main?.id ?? null) : result.item.source_id;
    const name = by === "topic" ? (main?.name ?? null) : result.item.source_name;
    const group = groups.get(key ?? "") ?? { key, name, results: [] };
    group.results.push(result);
    groups.set(key ?? "", group);
  }
  return [...groups.values()].sort((a, b) =>
    a.key === null || b.key === null
      ? Number(a.key === null) - Number(b.key === null)
      : (a.name ?? "").localeCompare(b.name ?? "", "fr", { sensitivity: "base" }),
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
