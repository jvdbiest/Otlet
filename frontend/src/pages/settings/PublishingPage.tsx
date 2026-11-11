// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { sitesQuery, useAddSite, useCheckSite, useDeleteSite, useUpdateSite, type SiteView } from "../../publishing.ts";
import { useWorkspaceId } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { SettingsTabs } from "./SettingsTabs.tsx";
import { publishingError, reasonText } from "./publishingReasons.ts";

function SiteForm({
  workspaceId,
  site,
  onDone,
}: {
  workspaceId: string;
  site: SiteView | null;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const add = useAddSite(workspaceId);
  const update = useUpdateSite(workspaceId);
  const [name, setName] = useState(site?.name ?? "");
  const [url, setUrl] = useState(site?.url ?? "");
  const [username, setUsername] = useState(site?.username ?? "");
  const [password, setPassword] = useState("");
  const saving = add.isPending || update.isPending;
  const error = publishingError(t, add.error ?? update.error);
  const prefix = site?.id ?? "new";
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        const body = { name, url, username, password: password === "" ? null : password };
        if (site === null) {
          add.mutate(body, { onSuccess: onDone });
        } else {
          update.mutate({ siteId: site.id, body }, { onSuccess: onDone });
        }
      }}
    >
      <div className={styles.field}>
        <label htmlFor={`site-name-${prefix}`}>{t("publishing.site.name")}</label>
        <input id={`site-name-${prefix}`} value={name} required onChange={(e) => { setName(e.target.value); }} />
      </div>
      <div className={styles.field}>
        <label htmlFor={`site-url-${prefix}`}>{t("publishing.site.url")}</label>
        <input
          id={`site-url-${prefix}`}
          value={url}
          required
          placeholder="https://monsite.be"
          onChange={(e) => {
            setUrl(e.target.value);
          }}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor={`site-user-${prefix}`}>{t("publishing.site.username")}</label>
        <input id={`site-user-${prefix}`} value={username} required autoComplete="off" onChange={(e) => { setUsername(e.target.value); }} />
      </div>
      <div className={styles.field}>
        <label htmlFor={`site-password-${prefix}`}>{t("publishing.site.password")}</label>
        <input
          id={`site-password-${prefix}`}
          type="password"
          value={password}
          required={site === null}
          autoComplete="new-password"
          placeholder={site === null ? "" : t("publishing.site.passwordKept", { hint: site.password_hint })}
          onChange={(e) => {
            setPassword(e.target.value);
          }}
        />
        <span className={styles.help}>{t("publishing.site.passwordHelp")}</span>
      </div>
      {error !== null && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      <p className={styles.row}>
        <button type="submit" className={styles.primary} disabled={saving}>
          {site === null ? t("publishing.site.add") : t("publishing.site.save")}
        </button>
        <button type="button" className={styles.button} onClick={onDone}>
          {t("publishing.site.cancel")}
        </button>
      </p>
    </form>
  );
}

function SiteCard({ workspaceId, site }: { workspaceId: string; site: SiteView }) {
  const { t } = useTranslation();
  const check = useCheckSite(workspaceId);
  const remove = useDeleteSite(workspaceId);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  if (editing) {
    return (
      <li className={styles.panel}>
        <SiteForm
          workspaceId={workspaceId}
          site={site}
          onDone={() => {
            setEditing(false);
          }}
        />
      </li>
    );
  }
  const ok = site.check_result === "ok";
  return (
    <li className={styles.panel}>
      <h3>{site.name}</h3>
      <p className={styles.meta}>
        {site.url} · {site.username} · {t("publishing.site.passwordEnds", { hint: site.password_hint })}
      </p>
      <p role="status" className={site.check_pending ? styles.meta : ok ? styles.success : styles.error}>
        {site.check_pending
          ? t("publishing.site.checking")
          : site.check_result === null
            ? t("publishing.site.neverChecked")
            : ok
              ? t("publishing.site.checkOk", {
                  role: site.check_role ?? "",
                  categories: site.categories.length,
                  tags: site.tags.length,
                  date: site.checked_at === null ? "" : formatDate(site.checked_at),
                })
              : `${reasonText(t, site.check_result)}${site.check_detail ? ` (${site.check_detail})` : ""}`}
      </p>
      {ok && site.check_role === "administrator" && <p className={styles.warning}>{t("publishing.site.adminWarning")}</p>}
      <p className={styles.row}>
        <button
          type="button"
          className={styles.button}
          disabled={check.isPending || site.check_pending}
          onClick={() => {
            check.mutate(site.id);
          }}
        >
          {t("publishing.site.check")}
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={() => {
            setEditing(true);
          }}
        >
          {t("publishing.site.edit")}
        </button>
        {confirming ? (
          <>
            <span>{t("publishing.site.confirmDelete")}</span>
            <button
              type="button"
              className={styles.danger}
              disabled={remove.isPending}
              onClick={() => {
                remove.mutate(site.id);
              }}
            >
              {t("publishing.site.delete")}
            </button>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setConfirming(false);
              }}
            >
              {t("publishing.site.cancel")}
            </button>
          </>
        ) : (
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setConfirming(true);
            }}
          >
            {t("publishing.site.delete")}
          </button>
        )}
      </p>
    </li>
  );
}

/** Réglages › Publication (U07): the WordPress sites the articles of the Library go to. */
export function PublishingPage() {
  const { t } = useTranslation();
  const workspaceId = useWorkspaceId();
  const sites = useQuery({ ...sitesQuery(workspaceId ?? ""), enabled: workspaceId !== undefined });
  const [adding, setAdding] = useState(false);
  if (workspaceId === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  return (
    <div className={styles.article}>
      <h1>{t("publishing.title")}</h1>
      <SettingsTabs />
      <p className={styles.help}>{t("publishing.intro")}</p>
      <p className={styles.help}>{t("publishing.howTo")}</p>
      {sites.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, sites.error)}
        </p>
      )}
      <ul className={styles.list}>
        {(sites.data ?? []).map((site) => (
          <SiteCard key={site.id} workspaceId={workspaceId} site={site} />
        ))}
      </ul>
      {sites.data?.length === 0 && !adding && <p className={styles.meta}>{t("publishing.none")}</p>}
      {adding ? (
        <section className={styles.panel} aria-labelledby="site-new">
          <h2 id="site-new">{t("publishing.site.new")}</h2>
          <SiteForm
            workspaceId={workspaceId}
            site={null}
            onDone={() => {
              setAdding(false);
            }}
          />
        </section>
      ) : (
        <p>
          <button
            type="button"
            className={styles.primary}
            onClick={() => {
              setAdding(true);
            }}
          >
            {t("publishing.site.new")}
          </button>
        </p>
      )}
    </div>
  );
}
