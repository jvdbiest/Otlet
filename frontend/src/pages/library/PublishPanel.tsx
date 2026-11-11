// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { eventsQuery, publicationsQuery, sitesQuery, useSendToSite, type PublicationView, type SiteView } from "../../publishing.ts";
import { formatDate, isWebUrl } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { publishingError, reasonText } from "../settings/publishingReasons.ts";

function Journal({ workspaceId, publication }: { workspaceId: string; publication: PublicationView }) {
  const { t } = useTranslation();
  const events = useQuery(eventsQuery(workspaceId, publication.id));
  return (
    <ul className={styles.list}>
      {(events.data ?? []).map((e, index) => (
        <li key={index} className={styles.meta}>
          {e.at === null ? "" : formatDate(e.at)} · {t(`publishing.action.${e.action === "publish" ? "publish" : "draft"}`)} ·{" "}
          {t("publishing.versionN", { number: e.version })} · {e.result === "done" ? t("publishing.done") : reasonText(t, e.result)}
          {e.detail ? ` (${e.detail})` : ""}
        </li>
      ))}
    </ul>
  );
}

function Status({
  workspaceId,
  publication,
  site,
  validated,
}: {
  workspaceId: string;
  publication: PublicationView;
  site: SiteView | undefined;
  validated: number | null;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const name = site?.name ?? "";
  const where =
    publication.remote_status === "publish"
      ? t("publishing.onSite.published", { site: name })
      : publication.remote_status === "draft"
        ? t("publishing.onSite.draft", { site: name })
        : t("publishing.onSite.none", { site: name });
  return (
    <div>
      <p className={styles.row}>
        <span className={styles.badge}>{where}</span>
        {publication.remote_url !== null && isWebUrl(publication.remote_url) && (
          <a href={publication.remote_url} target="_blank" rel="noopener">
            {t("publishing.open")}
          </a>
        )}
        {publication.version !== null && publication.sent_at !== null && (
          <span className={styles.meta}>
            {t("publishing.sentVersion", { number: publication.version, date: formatDate(publication.sent_at) })}
          </span>
        )}
        <button
          type="button"
          className={styles.linkButton}
          onClick={() => {
            setOpen(!open);
          }}
        >
          {open ? t("publishing.hideJournal") : t("publishing.showJournal")}
        </button>
      </p>
      {publication.state === "pending" && (
        <p role="status" className={styles.meta}>
          {t(publication.action === "publish" ? "publishing.pendingPublish" : "publishing.pendingDraft")}
        </p>
      )}
      {(publication.state === "failed" || publication.state === "to_check") && (
        <p role="alert" className={styles.error}>
          {reasonText(t, publication.error)}
        </p>
      )}
      {validated !== null && publication.version !== null && publication.version < validated && (
        <p className={styles.warning}>{t("publishing.outdated", { sent: publication.version, validated })}</p>
      )}
      {open && <Journal workspaceId={workspaceId} publication={publication} />}
    </div>
  );
}

/** Send the validated version to a WordPress site (U07): « Envoyer en brouillon » first and most
 * visible; « Publier » apart, after a confirmation that names the site and the article. */
export function PublishPanel({
  workspaceId,
  articleId,
  title,
  validated,
}: {
  workspaceId: string;
  articleId: string;
  title: string;
  validated: number | null;
}) {
  const { t } = useTranslation();
  const sites = useQuery(sitesQuery(workspaceId));
  const publications = useQuery(publicationsQuery(workspaceId, articleId));
  const send = useSendToSite(workspaceId);
  const list = sites.data ?? [];
  const [siteId, setSiteId] = useState<string>("");
  const site = list.find((s) => s.id === siteId) ?? list[0];
  const current = (publications.data ?? []).find((p) => p.site_id === site?.id);
  const [categories, setCategories] = useState<number[] | null>(null);
  const [tags, setTags] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const chosenCategories = categories ?? current?.categories ?? [];
  const typedTags = tags ?? (current?.tags ?? []).join(", ");
  const published = current?.remote_status === "publish";
  const pending = current?.state === "pending";
  const error = publishingError(t, send.error);
  if (sites.data !== undefined && list.length === 0) {
    return (
      <section className={styles.panel} aria-labelledby="publish-title">
        <h2 id="publish-title">{t("publishing.panel.title")}</h2>
        <p className={styles.meta}>
          {t("publishing.panel.noSite")} <Link to="/reglages/publication">{t("publishing.panel.addSite")}</Link>
        </p>
      </section>
    );
  }
  if (site === undefined) {
    return null;
  }
  const go = (action: "draft" | "publish") => {
    send.mutate(
      {
        articleId,
        body: {
          site_id: site.id,
          action,
          categories: chosenCategories,
          tags: typedTags
            .split(",")
            .map((tag) => tag.trim())
            .filter((tag) => tag !== ""),
        },
      },
      {
        onSuccess: () => {
          setConfirming(false);
        },
      },
    );
  };
  return (
    <section className={styles.panel} aria-labelledby="publish-title">
      <h2 id="publish-title">{t("publishing.panel.title")}</h2>
      {validated === null ? (
        <p className={styles.meta}>{t("publishing.panel.notValidated")}</p>
      ) : (
        <>
          {list.length > 1 && (
            <div className={styles.field}>
              <label htmlFor="publish-site">{t("publishing.panel.site")}</label>
              <select
                id="publish-site"
                value={site.id}
                onChange={(event) => {
                  setSiteId(event.target.value);
                  setCategories(null);
                  setTags(null);
                }}
              >
                {list.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {current !== undefined && <Status workspaceId={workspaceId} publication={current} site={site} validated={validated} />}
          {site.categories.length > 0 && (
            <fieldset className={styles.choices}>
              <legend>{t("publishing.panel.categories")}</legend>
              {site.categories.map((c) => (
                <label key={c.id}>
                  <input
                    type="checkbox"
                    checked={chosenCategories.includes(c.id)}
                    onChange={(event) => {
                      setCategories(
                        event.target.checked ? [...chosenCategories, c.id] : chosenCategories.filter((id) => id !== c.id),
                      );
                    }}
                  />{" "}
                  {c.name}
                </label>
              ))}
            </fieldset>
          )}
          <div className={styles.field}>
            <label htmlFor="publish-tags">{t("publishing.panel.tags")}</label>
            <input
              id="publish-tags"
              list="publish-tags-known"
              value={typedTags}
              placeholder={t("publishing.panel.tagsPlaceholder")}
              onChange={(event) => {
                setTags(event.target.value);
              }}
            />
            <datalist id="publish-tags-known">
              {site.tags.map((tag) => (
                <option key={tag.id} value={tag.name} />
              ))}
            </datalist>
            <span className={styles.help}>{t("publishing.panel.tagsHelp")}</span>
          </div>
          {site.check_result !== "ok" && !site.check_pending && (
            <p className={styles.warning}>
              {t("publishing.panel.notChecked")} <Link to="/reglages/publication">{t("publishing.panel.toSettings")}</Link>
            </p>
          )}
          {confirming ? (
            <div className={styles.notice} role="alertdialog" aria-labelledby="publish-confirm">
              <p id="publish-confirm">
                <strong>
                  {published
                    ? t("publishing.confirm.update", { site: site.name, title })
                    : t("publishing.confirm.publish", { site: site.name, title })}
                </strong>
              </p>
              <p className={styles.help}>{t("publishing.confirm.help", { number: validated })}</p>
              <p className={styles.row}>
                <button
                  type="button"
                  className={styles.danger}
                  disabled={send.isPending || pending}
                  onClick={() => {
                    go("publish");
                  }}
                >
                  {published ? t("publishing.confirm.updateNow") : t("publishing.confirm.publishNow")}
                </button>
                <button
                  type="button"
                  className={styles.button}
                  onClick={() => {
                    setConfirming(false);
                  }}
                >
                  {t("publishing.confirm.cancel")}
                </button>
              </p>
            </div>
          ) : (
            <p className={styles.row}>
              {!published && (
                <button
                  type="button"
                  className={styles.primary}
                  disabled={send.isPending || pending}
                  onClick={() => {
                    go("draft");
                  }}
                >
                  {current?.remote_status === "draft"
                    ? t("publishing.panel.updateDraft", { site: site.name })
                    : t("publishing.panel.sendDraft", { site: site.name })}
                </button>
              )}
              <button
                type="button"
                className={published ? styles.primary : styles.button}
                disabled={send.isPending || pending}
                onClick={() => {
                  setConfirming(true);
                }}
              >
                {published ? t("publishing.panel.updatePublished") : t("publishing.panel.publish")}
              </button>
            </p>
          )}
          {published && <p className={styles.help}>{t("publishing.panel.publishedHelp")}</p>}
          {error !== null && (
            <p role="alert" className={styles.error}>
              {error}
            </p>
          )}
        </>
      )}
    </section>
  );
}
