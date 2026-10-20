// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Form, Input, Label, Text, TextField } from "react-aria-components";
import { useTranslation } from "react-i18next";
import {
  checksQuery,
  sourcesQuery,
  useAddSource,
  useCollectNow,
  useDeleteSource,
  useUpdateSource,
  type SourceView,
} from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import {
  errorText,
  formatDate,
  INTERVALS,
  isWebUrl,
  legalLabel,
  legalTone,
  matchesFilter,
  reasonText,
} from "./labels.ts";
import { SourceRights } from "./SourceRights.tsx";
import { emptyStyles, styles } from "./styles.ts";

/** The sources of the workspace: adding one, their legal status and health (U01, M-08). */
export function SourcesPage() {
  const workspaceId = useWorkspaceId();
  return workspaceId === undefined ? null : <Sources workspaceId={workspaceId} />;
}

function Sources({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const sources = useQuery(sourcesQuery(workspaceId));
  const [query, setQuery] = useState("");
  const shown = (sources.data ?? []).filter(
    (source) => matchesFilter(source.name, query) || matchesFilter(source.feed_url, query),
  );
  return (
    <>
      <AddSource workspaceId={workspaceId} />
      <h2>{t("sources.title")}</h2>
      {sources.data !== undefined && sources.data.length > 0 && (
        <div className={`${styles.field} ${styles.filter}`}>
          <label htmlFor="sources-filter">{t("sources.filter")}</label>
          <input
            id="sources-filter"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
        </div>
      )}
      {sources.data !== undefined && sources.data.length > 0 && shown.length === 0 && (
        <p role="status" className={styles.meta}>
          {t("sources.noMatch", { q: query.trim() })}
        </p>
      )}
      {sources.isError && <p role="alert">{t("watch.loadFailed")}</p>}
      {sources.data?.length === 0 && (
        <div className={emptyStyles.empty}>
          <p className={emptyStyles.headline}>{t("sources.empty")}</p>
        </div>
      )}
      {shown.length > 0 && (
        <ul className={styles.list}>
          {shown.map((source) => (
            <SourceCard key={source.id} workspaceId={workspaceId} source={source} />
          ))}
        </ul>
      )}
    </>
  );
}

function AddSource({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const add = useAddSource(workspaceId);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [interval, setFrequency] = useState("60");
  const [added, setAdded] = useState<string | null>(null);

  return (
    <section className={styles.panel} aria-labelledby="add-source">
      <h2 id="add-source">{t("sources.add.title")}</h2>
      <Form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          setAdded(null);
          add.mutate(
            { url, interval_minutes: Number(interval), ...(name.trim() ? { name: name.trim() } : {}) },
            {
              onSuccess: (source) => {
                setAdded(source.name);
                setUrl("");
                setName("");
              },
            },
          );
        }}
      >
        <TextField className={styles.field} value={url} onChange={setUrl} isRequired type="text" inputMode="url">
          <Label>{t("sources.add.url")}</Label>
          <Input placeholder="https://" autoComplete="url" />
          <Text slot="description" className={styles.help}>
            {t("sources.add.urlHelp")}
          </Text>
        </TextField>
        <TextField className={styles.field} value={name} onChange={setName} maxLength={200}>
          <Label>{t("sources.add.name")}</Label>
          <Input />
        </TextField>
        <div className={styles.field}>
          <label htmlFor="source-interval">{t("sources.add.interval")}</label>
          <select
            id="source-interval"
            value={interval}
            onChange={(event) => {
              setFrequency(event.target.value);
            }}
          >
            {INTERVALS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {t(`sources.intervals.${minutes}`)}
              </option>
            ))}
          </select>
        </div>
        <p className={styles.notice}>{t("sources.add.notice")}</p>
        {add.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, add.error)}
          </p>
        )}
        {added !== null && (
          <p role="status" className={styles.success}>
            {t("sources.add.added", { name: added })}
          </p>
        )}
        <Button type="submit" className={styles.primary} isDisabled={add.isPending}>
          {add.isPending ? t("sources.add.submitting") : t("sources.add.submit")}
        </Button>
      </Form>
    </section>
  );
}

/** Changes a source (Joël, 2026-10-20): its name, its address (the site or its feed, checked
 * again as when it was added), how often it is collected. */
function SourceEdit({ workspaceId, source, onDone }: { workspaceId: string; source: SourceView; onDone: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateSource(workspaceId);
  const [name, setName] = useState(source.name);
  const [url, setUrl] = useState(source.url);
  const [interval, setInterval] = useState(String(source.interval_minutes));
  const prefix = `source-edit-${source.id}`;
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate(
          {
            sourceId: source.id,
            ...(name.trim() !== source.name ? { name: name.trim() } : {}),
            ...(Number(interval) !== source.interval_minutes ? { interval_minutes: Number(interval) } : {}),
            ...(url.trim() !== source.url ? { url: url.trim() } : {}),
          },
          { onSuccess: onDone },
        );
      }}
    >
      <div className={styles.field}>
        <label htmlFor={`${prefix}-name`}>{t("sources.add.name")}</label>
        <input
          id={`${prefix}-name`}
          required
          maxLength={200}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor={`${prefix}-url`}>{t("sources.edit.url")}</label>
        <input
          id={`${prefix}-url`}
          required
          type="url"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
          }}
        />
        <span className={styles.help}>{t("sources.edit.urlHelp")}</span>
      </div>
      <div className={styles.field}>
        <label htmlFor={`${prefix}-interval`}>{t("sources.add.interval")}</label>
        <select
          id={`${prefix}-interval`}
          value={interval}
          onChange={(event) => {
            setInterval(event.target.value);
          }}
        >
          {INTERVALS.map((minutes) => (
            <option key={minutes} value={minutes}>
              {t(`sources.intervals.${minutes}`)}
            </option>
          ))}
        </select>
      </div>
      {update.error !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, update.error)}
        </p>
      )}
      <p className={styles.row}>
        <button type="submit" className={styles.primary} disabled={update.isPending}>
          {update.isPending ? t("sources.edit.saving") : t("sources.edit.save")}
        </button>
        <button type="button" className={styles.button} onClick={onDone}>
          {t("brief.cancel")}
        </button>
      </p>
    </form>
  );
}

function SourceCard({ workspaceId, source }: { workspaceId: string; source: SourceView }) {
  const { t } = useTranslation();
  const update = useUpdateSource(workspaceId);
  const collect = useCollectNow(workspaceId);
  const remove = useDeleteSource(workspaceId);
  const [confirming, setConfirming] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const [editing, setEditing] = useState(false);
  const failed = update.error ?? collect.error ?? remove.error;
  const headingId = `source-${source.id}`;

  return (
    <li className={styles.card} aria-labelledby={headingId}>
      <h3 id={headingId}>
        {source.site_url !== null && isWebUrl(source.site_url) ? (
          <a href={source.site_url} target="_blank" rel="noopener noreferrer nofollow">
            {source.name}
          </a>
        ) : (
          source.name
        )}
      </h3>
      <p className={styles.meta}>{source.feed_url}</p>
      <p className={styles.row}>
        <span className={styles[legalTone(source.legal_status)]}>{legalLabel(t, source.legal_status)}</span>
        <span className={styles.meta}>{reasonText(t, source.legal_reason)}</span>
      </p>
      <p className={styles.meta}>
        {t("sources.items", { count: source.item_count })}
        {" · "}
        {!source.active
          ? t("sources.paused")
          : source.last_fetched_at === null
            ? t("sources.neverFetched")
            : t("sources.lastFetched", { date: formatDate(source.last_fetched_at) })}
        {" · "}
        {t(`sources.health.${source.health === "dead" || source.health === "degraded" ? source.health : "ok"}`, {
          count: source.consecutive_failures,
        })}
      </p>
      {source.last_error !== null && (
        <p className={styles.meta}>{t("sources.lastError", { reason: reasonText(t, source.last_error) })}</p>
      )}
      <div className={styles.row}>
        {source.active && (
          <Button
            className={styles.button}
            isDisabled={collect.isPending}
            onPress={() => {
              collect.mutate(source.id);
            }}
          >
            {t("sources.collectNow")}
          </Button>
        )}
        <Button
          className={styles.button}
          isDisabled={update.isPending}
          onPress={() => {
            update.mutate({ sourceId: source.id, active: !source.active });
          }}
        >
          {source.active ? t("sources.pause") : t("sources.resume")}
        </Button>
        <Button
          className={styles.button}
          aria-expanded={editing}
          onPress={() => {
            setEditing((open) => !open);
          }}
        >
          {t("sources.edit.open")}
        </Button>
        <Button
          className={styles.button}
          aria-expanded={showJournal}
          onPress={() => {
            setShowJournal((shown) => !shown);
          }}
        >
          {t("sources.journal")}
        </Button>
        {!confirming ? (
          <Button
            className={styles.danger}
            onPress={() => {
              setConfirming(true);
            }}
          >
            {t("sources.delete")}
          </Button>
        ) : (
          <span className={styles.row} role="group" aria-label={t("sources.confirmDelete")}>
            <span>{t("sources.confirmDelete")}</span>
            <Button
              className={styles.danger}
              isDisabled={remove.isPending}
              autoFocus
              onPress={() => {
                remove.mutate(source.id);
              }}
            >
              {t("sources.confirm")}
            </Button>
            <Button
              className={styles.button}
              onPress={() => {
                setConfirming(false);
              }}
            >
              {t("sources.cancel")}
            </Button>
          </span>
        )}
      </div>
      {failed !== null && (
        <p role="alert" className={styles.error}>
          {t("sources.actionFailed")}
        </p>
      )}
      <SourceRights
        workspaceId={workspaceId}
        sourceId={source.id}
        reserved={source.legal_reason?.startsWith("tdm_reserved") === true}
      />
      {editing && (
        <SourceEdit
          workspaceId={workspaceId}
          source={source}
          onDone={() => {
            setEditing(false);
          }}
        />
      )}
      {showJournal && <Journal workspaceId={workspaceId} sourceId={source.id} />}
    </li>
  );
}

function Journal({ workspaceId, sourceId }: { workspaceId: string; sourceId: string }) {
  const { t } = useTranslation();
  const checks = useQuery(checksQuery(workspaceId, sourceId));
  if (checks.data === undefined) {
    return checks.isError ? <p role="alert">{t("watch.loadFailed")}</p> : <p>{t("app.loading")}</p>;
  }
  if (checks.data.length === 0) {
    return <p className={styles.meta}>{t("sources.journalEmpty")}</p>;
  }
  return (
    <ul className={styles.journal}>
      {checks.data.map((check) => (
        <li key={`${check.checked_at}-${check.reason}`}>
          {t("sources.journalEntry", {
            date: formatDate(check.checked_at),
            decision: check.allowed ? t("sources.allowed") : t("sources.refusedDecision"),
          })}{" "}
          {reasonText(t, check.reason)}
          {check.detail !== "" && isWebUrl(check.detail) && (
            <>
              {" "}
              <a href={check.detail} target="_blank" rel="noopener noreferrer nofollow">
                {t("sources.policy")}
              </a>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
