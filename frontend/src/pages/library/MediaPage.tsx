// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import {
  IMAGE_TYPES,
  mediaDetailsQuery,
  mediaListQuery,
  mediaTagsQuery,
  mediaUrl,
  thumbnailUrl,
  uploadImage,
  useDescribeMedia,
  useMediaAction,
  useSetMediaTags,
  type MediaAction,
  type MediaDescription,
  type MediaEntryView,
  type MediaSection,
  type MediaView,
} from "../../media.ts";
import { workspacesQuery } from "../../session.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import css from "./media.module.css";

const local = css as Record<"grid" | "tile" | "thumb" | "sheet" | "preview" | "sections", string>;

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${String(Math.max(1, Math.round(bytes / 1024)))} Ko` : `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
}

/** Imports images into the bank of images, one after the other. */
function ImportImages({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(0);
  const [failure, setFailure] = useState<Error | null>(null);
  return (
    <p className={styles.row}>
      <label className={styles.button}>
        {t("media.import")}
        <input
          type="file"
          accept={IMAGE_TYPES.join(",")}
          multiple
          hidden
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            setFailure(null);
            setPending(files.length);
            void (async () => {
              for (const file of files) {
                try {
                  await uploadImage(workspaceId, file, true);
                } catch (error: unknown) {
                  setFailure(error instanceof Error ? error : new Error(String(error)));
                }
                setPending((n) => n - 1);
              }
              await queryClient.invalidateQueries({ queryKey: ["workspaces", workspaceId] });
            })();
          }}
        />
      </label>
      {pending > 0 && <span className={styles.meta}>{t("media.importing", { count: pending })}</span>}
      {failure !== null && (
        <span role="alert" className={styles.error}>
          {errorText(t, failure)}
        </span>
      )}
    </p>
  );
}

function describe(media: MediaView): MediaDescription {
  return {
    name: media.name ?? "",
    description: media.description ?? "",
    credit: media.credit ?? "",
    licence: media.licence ?? "",
    source_url: media.source_url ?? "",
  };
}

/** The tags of an image, typed separated by commas, as for the articles. */
function MediaTags({ workspaceId, media }: { workspaceId: string; media: MediaView }) {
  const { t } = useTranslation();
  const setTags = useSetMediaTags(workspaceId);
  const [typed, setTyped] = useState(media.tags.join(", "));
  return (
    <form
      className={styles.row}
      onSubmit={(event) => {
        event.preventDefault();
        setTags.mutate({ mediaId: media.id, tags: typed.split(",") });
      }}
    >
      <label>
        {t("media.tags")}{" "}
        <input
          value={typed}
          placeholder={t("library.tagsPlaceholder")}
          onChange={(event) => {
            setTyped(event.target.value);
          }}
        />
      </label>
      <button type="submit" className={styles.button} disabled={setTags.isPending}>
        {t("library.saveTags")}
      </button>
      {setTags.error !== null && (
        <span role="alert" className={styles.error}>
          {setTags.error instanceof ApiError && setTags.error.detail === "invalid_tags"
            ? t("media.errors.invalid_tags")
            : errorText(t, setTags.error)}
        </span>
      )}
    </form>
  );
}

/** The sheet of an image: what it is, what a person says of it, where it is used. */
function MediaSheet({ workspaceId, mediaId, onClose }: { workspaceId: string; mediaId: string; onClose: () => void }) {
  const { t } = useTranslation();
  const details = useQuery(mediaDetailsQuery(workspaceId, mediaId));
  const save = useDescribeMedia(workspaceId);
  const act = useMediaAction(workspaceId);
  const [draft, setDraft] = useState<MediaDescription | null>(null);
  const [saved, setSaved] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  // A new sheet for each image (its `key`): only the focus moves to it.
  useEffect(() => {
    heading.current?.focus();
  }, [mediaId]);
  if (details.data === undefined) {
    return null;
  }
  const { media, usages } = details.data;
  const form = draft ?? describe(media);
  const field = (key: keyof MediaDescription, label: string, help?: string, long = false) => (
    <p className={styles.field}>
      <label htmlFor={`media-${key}`}>{label}</label>
      {long ? (
        <textarea
          id={`media-${key}`}
          rows={3}
          maxLength={500}
          value={form[key]}
          onChange={(event) => {
            setDraft({ ...form, [key]: event.target.value });
            setSaved(false);
          }}
        />
      ) : (
        <input
          id={`media-${key}`}
          type={key === "source_url" ? "url" : "text"}
          value={form[key]}
          onChange={(event) => {
            setDraft({ ...form, [key]: event.target.value });
            setSaved(false);
          }}
        />
      )}
      {help && <span className={styles.help}>{help}</span>}
    </p>
  );
  const saveError =
    save.error instanceof ApiError && (save.error.detail === "too_long" || save.error.detail === "invalid_url")
      ? t(`media.errors.${save.error.detail}`)
      : save.error !== null
        ? errorText(t, save.error)
        : null;
  return (
    <section className={styles.panel} aria-labelledby="media-sheet-title">
      <div className={styles.row}>
        <h2 id="media-sheet-title" ref={heading} tabIndex={-1}>
          {media.name ?? t("media.unnamed")}
        </h2>
        <button type="button" className={styles.button} onClick={onClose}>
          {t("media.sheet.close")}
        </button>
      </div>
      <div className={local.sheet}>
        <div>
          <img className={local.preview} src={mediaUrl(workspaceId, media.id)} alt={media.description ?? ""} />
          <p className={styles.meta}>
            {t("media.sheet.facts", {
              width: media.width,
              height: media.height,
              size: formatSize(media.size),
              date: formatDate(media.created_at),
            })}
          </p>
          <p className={styles.meta}>{t(`media.origins.${media.origin}`)}</p>
          <MediaTags key={media.tags.join("|")} workspaceId={workspaceId} media={media} />
          <h3>{t("media.sheet.usedIn")}</h3>
          {usages.length === 0 ? (
            <p className={styles.meta}>{t("media.sheet.notUsed")}</p>
          ) : (
            <ul>
              {usages.map((usage) => (
                <li key={usage.article_id}>
                  <Link to="/bibliotheque/articles/$articleId" params={{ articleId: usage.article_id }}>
                    {usage.title}
                  </Link>{" "}
                  <span className={styles.meta}>
                    ({t(`library.status.${usage.status as "brouillon" | "valide" | "archive"}`)},{" "}
                    {t("media.sheet.versions", { count: usage.versions.length, list: usage.versions.join(", ") })})
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className={styles.row}>
            <button
              type="button"
              className={styles.button}
              disabled={act.isPending}
              onClick={() => {
                act.mutate({ action: media.in_bank ? "unkeep" : "keep", mediaIds: [media.id] });
              }}
            >
              {t(media.in_bank ? "media.selection.unkeep" : "media.selection.keep")}
            </button>
            <button
              type="button"
              className={styles.button}
              disabled={act.isPending || usages.length > 0}
              title={usages.length > 0 ? t("media.sheet.deleteBlocked") : undefined}
              onClick={() => {
                if (window.confirm(t("media.selection.confirmDelete", { count: 1 }))) {
                  act.mutate({ action: "delete", mediaIds: [media.id] }, { onSuccess: onClose });
                }
              }}
            >
              {t("media.selection.delete")}
            </button>
          </p>
        </div>
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(
              { mediaId: media.id, description: form },
              {
                onSuccess: () => {
                  setDraft(null);
                  setSaved(true);
                },
              },
            );
          }}
        >
          {field("name", t("media.sheet.name"))}
          {field("description", t("media.sheet.description"), t("media.sheet.descriptionHelp"), true)}
          {field("credit", t("media.sheet.credit"))}
          {field("licence", t("media.sheet.licence"), t("media.sheet.licenceHelp"))}
          {field("source_url", t("media.sheet.sourceUrl"))}
          <p className={styles.row}>
            <button type="submit" className={styles.primary} disabled={save.isPending || draft === null}>
              {t("media.sheet.save")}
            </button>
            {saved && (
              <span role="status" className={styles.meta}>
                {t("media.sheet.saved")}
              </span>
            )}
            {saveError !== null && (
              <span role="alert" className={styles.error}>
                {saveError}
              </span>
            )}
          </p>
        </form>
      </div>
    </section>
  );
}

/** The selection of images and its actions. Deleting refuses the images an article shows. */
function MediaBar({
  workspaceId,
  section,
  visible,
  selected,
  onSelect,
}: {
  workspaceId: string;
  section: MediaSection;
  visible: MediaEntryView[];
  selected: string[];
  onSelect: (ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const act = useMediaAction(workspaceId);
  const [done, setDone] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const all = useRef<HTMLInputElement>(null);
  const chosen = visible.filter((entry) => selected.includes(entry.id));
  const allSelected = visible.length > 0 && chosen.length === visible.length;
  useEffect(() => {
    if (all.current !== null) {
      all.current.indeterminate = chosen.length > 0 && !allSelected;
    }
  }, [chosen.length, allSelected]);
  if (visible.length === 0) {
    return done === null ? null : (
      <p className={styles.meta} role="status">
        {done}
      </p>
    );
  }
  const ids = chosen.map((entry) => entry.id);
  const run = (action: MediaAction) => {
    act.mutate(
      { action, mediaIds: ids },
      {
        onSuccess: (outcome) => {
          const message = t(`media.selection.done.${action}`, { count: outcome.done.length });
          const inUse = outcome.failed.filter((failed) => failed.reason === "in_use").length;
          setDone(inUse === 0 ? message : `${message} ${t("media.selection.inUse", { count: inUse })}`);
          setConfirming(false);
          onSelect([]);
        },
      },
    );
  };
  return (
    <div className={styles.bulkBar} role="region" aria-label={t("media.selection.label")}>
      <label className={styles.check}>
        <input
          ref={all}
          type="checkbox"
          checked={allSelected}
          onChange={(event) => {
            onSelect(event.target.checked ? visible.map((entry) => entry.id) : []);
            setDone(null);
            setConfirming(false);
          }}
        />{" "}
        {t("media.selection.all")}
      </label>
      <span className={styles.meta} aria-live="polite">
        {chosen.length > 0 ? t("media.selection.selected", { count: chosen.length }) : done}
      </span>
      {chosen.length > 0 && !confirming && (
        <div className={styles.row}>
          {section === "articles" ? (
            <button
              type="button"
              className={styles.button}
              disabled={act.isPending}
              onClick={() => {
                run("keep");
              }}
            >
              {t("media.selection.keep")}
            </button>
          ) : (
            <button
              type="button"
              className={styles.button}
              disabled={act.isPending}
              onClick={() => {
                run("unkeep");
              }}
            >
              {t("media.selection.unkeep")}
            </button>
          )}
          <button
            type="button"
            className={styles.button}
            disabled={act.isPending}
            onClick={() => {
              setConfirming(true);
            }}
          >
            {t("media.selection.delete")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              onSelect([]);
            }}
          >
            {t("media.selection.none")}
          </button>
        </div>
      )}
      {confirming && (
        <div className={styles.row} role="alertdialog" aria-label={t("media.selection.delete")}>
          <span>{t("media.selection.confirmDelete", { count: chosen.length })}</span>
          <button
            type="button"
            className={styles.primary}
            disabled={act.isPending}
            onClick={() => {
              run("delete");
            }}
          >
            {t("media.selection.deleteForGood")}
          </button>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setConfirming(false);
            }}
          >
            {t("media.selection.cancel")}
          </button>
        </div>
      )}
      {act.error !== null && (
        <span role="alert" className={styles.error}>
          {t("errors.generic")}
        </span>
      )}
    </div>
  );
}

/** The médiathèque (ADR-0040): one image, two views. The images of the articles, brought by the
 * work on them; the bank of images, those kept to be used again. */
export function MediaPage() {
  const { t } = useTranslation();
  const workspaces = useQuery(workspacesQuery);
  const workspaceId = workspaces.data?.[0]?.id ?? "";
  const [section, setSection] = useState<MediaSection>("articles");
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState("");
  const [used, setUsed] = useState<boolean | null>(null);
  const [tag, setTag] = useState("");
  const tags = useQuery({ ...mediaTagsQuery(workspaceId), enabled: workspaceId !== "" });
  const [selected, setSelected] = useState<string[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const list = useQuery({ ...mediaListQuery(workspaceId, section, query, used, tag), enabled: workspaceId !== "" });
  const entries = list.data ?? [];
  return (
    <>
      <div className={local.sections} role="group" aria-label={t("media.sections")}>
        {(["articles", "bank"] as const).map((name) => (
          <button
            key={name}
            type="button"
            className={name === section ? styles.primary : styles.button}
            aria-pressed={name === section}
            onClick={() => {
              setSection(name);
              setSelected([]);
            }}
          >
            {t(`media.${name}`)}
          </button>
        ))}
      </div>
      <p className={styles.help}>{t(section === "bank" ? "media.bankHelp" : "media.articlesHelp")}</p>
      {section === "bank" && <ImportImages workspaceId={workspaceId} />}
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
            aria-label={t("media.search")}
            placeholder={t("media.search")}
            value={typed}
            onChange={(event) => {
              setTyped(event.target.value);
              if (event.target.value === "") {
                setQuery("");
              }
            }}
          />
          <button type="submit" className={styles.button}>
            {t("media.searchButton")}
          </button>
          <select
            aria-label={t("media.usage")}
            value={used === null ? "" : String(used)}
            onChange={(event) => {
              setUsed(event.target.value === "" ? null : event.target.value === "true");
            }}
          >
            <option value="">{t("media.usageAll")}</option>
            <option value="true">{t("media.usageUsed")}</option>
            <option value="false">{t("media.usageUnused")}</option>
          </select>
          {(tags.data ?? []).length > 0 && (
            <select
              aria-label={t("media.tag")}
              value={tag}
              onChange={(event) => {
                setTag(event.target.value);
              }}
            >
              <option value="">{t("media.allTags")}</option>
              {(tags.data ?? []).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          )}
        </p>
      </form>
      {open !== null && (
        <MediaSheet
          key={open}
          workspaceId={workspaceId}
          mediaId={open}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
      <MediaBar
        workspaceId={workspaceId}
        section={section}
        visible={entries}
        selected={selected}
        onSelect={setSelected}
      />
      {list.data?.length === 0 && <p className={styles.help}>{query || used !== null || tag ? t("media.noMatch") : t("media.empty")}</p>}
      <ul className={local.grid}>
        {entries.map((entry) => {
          const name = entry.name ?? t("media.unnamed");
          const isSelected = selected.includes(entry.id);
          return (
            <li key={entry.id} className={isSelected ? `${local.tile} ${styles.selected}` : local.tile}>
              <button
                type="button"
                className={local.thumb}
                aria-label={t("media.open", { name })}
                onClick={() => {
                  setOpen(entry.id);
                }}
              >
                <img src={thumbnailUrl(workspaceId, entry.id)} alt="" loading="lazy" />
              </button>
              <p className={styles.cardHead}>
                <input
                  type="checkbox"
                  className={styles.select}
                  checked={isSelected}
                  aria-label={t("media.select", { name })}
                  onChange={(event) => {
                    setSelected((before) =>
                      event.target.checked ? [...before, entry.id] : before.filter((id) => id !== entry.id),
                    );
                  }}
                />
                <strong>{name}</strong>
              </p>
              <p className={styles.meta}>
                {entry.width} × {entry.height} · {entry.articles > 0 ? t("media.usedIn", { count: entry.articles }) : t("media.unused")}
              </p>
              {entry.tags.length > 0 && <p className={styles.meta}>{entry.tags.join(", ")}</p>}
              {section === "articles" && entry.in_bank && (
                <p>
                  <span className={styles.badge}>{t("media.inBank")}</span>
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
