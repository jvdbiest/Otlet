// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { itemQuery, useRemoveItem, useRetryText } from "../../collection.ts";
import { itemTriageQuery, useChangeTriage } from "../../triage.ts";
import { itemWatchQuery } from "../../watch.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText, explain, formatDate, isWebUrl, reasonText, retryable, textLabel, textTone } from "./labels.ts";
import { styles } from "./styles.ts";
import { ItemRights } from "./ItemRights.tsx";
import { TriageActions } from "./TriageActions.tsx";

/** One item, its text when Otlet may keep it, and where it comes from (U01, M-08). */
export function ItemPage({ itemId }: { itemId: string }) {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Item workspaceId={workspaceId} itemId={itemId} />;
}

function Item({ workspaceId, itemId }: { workspaceId: string; itemId: string }) {
  const { t } = useTranslation();
  const item = useQuery({
    ...itemQuery(workspaceId, itemId),
    // A page being read again: followed until its text is there.
    refetchInterval: (query) => (query.state.data?.text_status === "pending" ? 3_000 : false),
  });
  const retry = useRetryText(workspaceId);
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
        <span className={styles[textTone(data.text_status)]}>{textLabel(t, data.text_status, data.text_reason)}</span>
        <span className={styles.meta}>{reasonText(t, data.text_reason)}</span>
        {data.text_status === "summary_only" && retryable(data.text_reason) && (
          <button
            type="button"
            className={styles.button}
            disabled={retry.isPending}
            onClick={() => {
              retry.mutate(data.id);
            }}
          >
            {t("item.retryText")}
          </button>
        )}
      </p>
      {retry.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, retry.error)}
        </p>
      )}
      {data.url !== null && isWebUrl(data.url) && (
        <p>
          <a href={data.url} target="_blank" rel="noopener noreferrer nofollow">
            {t("item.original")}
          </a>
        </p>
      )}
      <ItemRights workspaceId={workspaceId} itemId={itemId} reason={data.text_reason} />
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
      <RemoveItem workspaceId={workspaceId} itemId={itemId} />
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

/** Removing an item for good: exceptional, so it lives here and asks first (decision of
 * Joël, 2026-10-17); the usual ways out of the feed are « Écarter » and « Archiver ». */
function RemoveItem({ workspaceId, itemId }: { workspaceId: string; itemId: string }) {
  const { t } = useTranslation();
  const remove = useRemoveItem(workspaceId);
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  return (
    <section className={styles.dangerZone} aria-labelledby="remove-item">
      <h3 id="remove-item">{t("item.remove.title")}</h3>
      <p className={styles.help}>{t("item.remove.help")}</p>
      {confirming ? (
        <div className={styles.row} role="alertdialog" aria-label={t("item.remove.title")}>
          <span>{t("item.remove.confirm")}</span>
          <button
            type="button"
            className={styles.danger}
            disabled={remove.isPending}
            onClick={() => {
              // Once removed, the page has nothing left to show: back to the feed, even if the
              // refreshed item has already unmounted this section.
              remove
                .mutateAsync(itemId)
                .then(() => navigate({ to: "/veille" }))
                .catch(() => undefined);
            }}
          >
            {t("item.remove.yes")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setConfirming(false);
            }}
          >
            {t("item.remove.no")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          className={styles.danger}
          onClick={() => {
            setConfirming(true);
          }}
        >
          {t("item.remove.button")}
        </button>
      )}
      {remove.error !== null && (
        <p role="alert" className={styles.error}>
          {t("errors.generic")}
        </p>
      )}
    </section>
  );
}
