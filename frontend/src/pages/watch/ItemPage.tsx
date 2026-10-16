// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { itemQuery } from "../../collection.ts";
import { itemTriageQuery, useChangeTriage } from "../../triage.ts";
import { itemWatchQuery } from "../../watch.ts";
import { useWorkspaceId } from "../../session.ts";
import { explain, formatDate, isWebUrl, reasonText, textLabel, textTone } from "./labels.ts";
import { styles } from "./styles.ts";
import { TriageActions } from "./TriageActions.tsx";

/** One item, its text when Otlet may keep it, and where it comes from (U01, M-08). */
export function ItemPage({ itemId }: { itemId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Item workspaceId={workspaceId} itemId={itemId} />;
}

function Item({ workspaceId, itemId }: { workspaceId: string; itemId: string }) {
  const { t } = useTranslation();
  const item = useQuery(itemQuery(workspaceId, itemId));
  const back = (
    <p>
      <Link to="/veille">{t("item.back")}</Link>
    </p>
  );
  if (item.isError) {
    const missing = item.error instanceof ApiError && item.error.status === 404;
    return (
      <>
        <p role="alert">{missing ? t("item.notFound") : t("watch.loadFailed")}</p>
        {back}
      </>
    );
  }
  if (item.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  const data = item.data;
  return (
    <article className={styles.article} aria-labelledby="item-title">
      {back}
      <h2 id="item-title">{data.title}</h2>
      <p className={styles.meta}>
        {data.source_name ?? t("watch.manualOrigin")}
        {data.author !== null && <> · {t("item.by", { author: data.author })}</>}
        {" · "}
        {data.published_at !== null
          ? t("item.published", { date: formatDate(data.published_at) })
          : t("item.collected", { date: formatDate(data.collected_at) })}
      </p>
      <p className={styles.row}>
        <span className={styles[textTone(data.text_status)]}>{textLabel(t, data.text_status)}</span>
        <span className={styles.meta}>{reasonText(t, data.text_reason)}</span>
      </p>
      {data.url !== null && isWebUrl(data.url) && (
        <p>
          <a href={data.url} target="_blank" rel="noopener noreferrer nofollow">
            {t("item.original")}
          </a>
        </p>
      )}
      {data.origin === "manual_text" && (
        <div className={styles.warning}>
          <p className={styles.success}>{t("item.manualNotice")}</p>
          <dl>
            <dt>{t("item.declaredOrigin")}</dt>
            <dd>{data.declared_origin}</dd>
            <dt>{t("item.usageRight")}</dt>
            <dd>{data.usage_right}</dd>
          </dl>
        </div>
      )}
      {data.summary !== null && (
        <section>
          <h3>{t("item.summary")}</h3>
          <p className={styles.text}>{data.summary}</p>
        </section>
      )}
      <ItemTriage workspaceId={workspaceId} itemId={itemId} title={data.title} />
      <ItemWatch workspaceId={workspaceId} itemId={itemId} />
      <section>
        <h3>{t("item.text")}</h3>
        {data.text === null ? (
          <p className={styles.meta}>{t("item.noText")}</p>
        ) : (
          <p className={styles.text}>{data.text}</p>
        )}
      </section>
    </article>
  );
}

/** The topics of the item with the reasons of each score, and the same story elsewhere (U02). */
function ItemWatch({ workspaceId, itemId }: { workspaceId: string; itemId: string }) {
  const { t } = useTranslation();
  const watch = useQuery(itemWatchQuery(workspaceId, itemId));
  if (watch.data === undefined) {
    return null;
  }
  return (
    <>
      <section>
        <h3>{t("item.topics")}</h3>
        {watch.data.topics.length === 0 ? (
          <p className={styles.meta}>{t("item.noTopic")}</p>
        ) : (
          <ul className={styles.journal}>
            {watch.data.topics.map((topic) => (
              <li key={topic.topic_id}>
                <Link to="/veille/sujets/$topicId" params={{ topicId: topic.topic_id }}>
                  {topic.name}
                </Link>{" "}
                ({t("item.points", { points: topic.score })}) : {explain(t, topic.contributions)}
              </li>
            ))}
          </ul>
        )}
      </section>
      {watch.data.duplicates.length > 0 && (
        <section>
          <h3>{t("item.sameStory")}</h3>
          <ul className={styles.journal}>
            {watch.data.duplicates.map((duplicate) => (
              <li key={duplicate.item_id}>
                <Link to="/veille/elements/$itemId" params={{ itemId: duplicate.item_id }}>
                  {duplicate.title}
                </Link>
                {duplicate.source_name !== null && <> · {duplicate.source_name}</>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/** The triage of the item; opening it marks it read (X02). */
function ItemTriage({ workspaceId, itemId, title }: { workspaceId: string; itemId: string; title: string }) {
  const triage = useQuery(itemTriageQuery(workspaceId, itemId));
  const change = useChangeTriage(workspaceId);
  const unread = triage.data?.read_at === null;
  const { mutate } = change;
  useEffect(() => {
    if (unread) {
      mutate({ itemId, change: { read: true } });
    }
  }, [unread, mutate, itemId]);
  if (triage.data === undefined) {
    return null;
  }
  return (
    <TriageActions workspaceId={workspaceId} itemId={itemId} title={title} triage={triage.data} showUnread />
  );
}
