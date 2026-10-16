// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { useWorkspaceId } from "../../session.ts";
import { TOPIC_PAGE_SIZE, topicItemsQuery, topicQuery, type ScoredItemView } from "../../watch.ts";
import { explain, formatDate, textLabel, textTone } from "./labels.ts";
import { RescoreStatus } from "./RescoreStatus.tsx";
import { emptyStyles, styles } from "./styles.ts";

/** The items of one topic, best score first, each with the reasons of its score (F-VEI-02). */
export function TopicItemsPage({ topicId }: { topicId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <TopicItems workspaceId={workspaceId} topicId={topicId} />;
}

function TopicItems({ workspaceId, topicId }: { workspaceId: string; topicId: string }) {
  const { t } = useTranslation();
  const topic = useQuery(topicQuery(workspaceId, topicId));
  const [pages, setPages] = useState(1);
  const queryClient = useQueryClient();
  const rescoring = topic.data?.rescoring;
  // When the recalculation ends, the list shows its result at once.
  useEffect(() => {
    if (rescoring === false) {
      void queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId, "topics", topicId, "items"] });
    }
  }, [rescoring, queryClient, workspaceId, topicId]);
  const back = (
    <p>
      <Link to="/veille/sujets">{t("topics.back")}</Link>
    </p>
  );
  if (topic.isError) {
    const missing = topic.error instanceof ApiError && topic.error.status === 404;
    return (
      <>
        <p role="alert">{missing ? t("pages.notFound.title") : t("watch.loadFailed")}</p>
        {back}
      </>
    );
  }
  if (topic.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  return (
    <>
      {back}
      <h2>{topic.data.name}</h2>
      <p className={styles.meta}>{t("topics.keywordsLabel", { terms: topic.data.keywords.join(", ") })}</p>
      <RescoreStatus workspaceId={workspaceId} topic={topic.data} />
      {Array.from({ length: pages }, (_, index) => (
        <ScoredPage
          key={index}
          workspaceId={workspaceId}
          topicId={topicId}
          offset={index * TOPIC_PAGE_SIZE}
          isLast={index === pages - 1}
          onMore={() => {
            setPages((count) => count + 1);
          }}
        />
      ))}
    </>
  );
}

function ScoredPage({
  workspaceId,
  topicId,
  offset,
  isLast,
  onMore,
}: {
  workspaceId: string;
  topicId: string;
  offset: number;
  isLast: boolean;
  onMore: () => void;
}) {
  const { t } = useTranslation();
  const items = useQuery(topicItemsQuery(workspaceId, topicId, offset));
  if (items.isError) {
    return <p role="alert">{t("watch.loadFailed")}</p>;
  }
  if (items.data === undefined) {
    return offset === 0 ? <p>{t("app.loading")}</p> : null;
  }
  if (items.data.length === 0 && offset === 0) {
    return (
      <div className={emptyStyles.empty}>
        <p className={emptyStyles.headline}>{t("topics.itemsEmpty")}</p>
      </div>
    );
  }
  return (
    <>
      <ul className={styles.list}>
        {items.data.map((entry) => (
          <ScoredCard key={entry.item.id} entry={entry} />
        ))}
      </ul>
      {isLast && items.data.length === TOPIC_PAGE_SIZE && (
        <p>
          <button type="button" className={styles.button} onClick={onMore}>
            {t("topics.more")}
          </button>
        </p>
      )}
    </>
  );
}

function ScoredCard({ entry }: { entry: ScoredItemView }) {
  const { t } = useTranslation();
  const item = entry.item;
  return (
    <li className={styles.card}>
      <h3>
        <Link to="/veille/elements/$itemId" params={{ itemId: item.id }}>
          {item.title}
        </Link>
      </h3>
      <p className={styles.meta}>
        {item.source_name ?? t("watch.manualOrigin")} · {formatDate(item.published_at ?? item.collected_at)}{" "}
        <span className={styles[textTone(item.text_status)]}>{textLabel(t, item.text_status)}</span>
        {item.duplicates > 0 && <> · {t("watch.duplicates", { count: item.duplicates })}</>}
      </p>
      <p className={styles.why}>
        <strong>{t("topics.score", { score: entry.score })}</strong>{" "}
        {t("topics.why", { reasons: explain(t, entry.contributions, entry.freshness) })}
      </p>
    </li>
  );
}
