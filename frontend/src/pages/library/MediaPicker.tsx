// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  mediaListQuery,
  mediaTagsQuery,
  thumbnailUrl,
  type MediaEntryView,
  type MediaSection,
} from "../../media.ts";
import { styles } from "../watch/styles.ts";
import css from "./media.module.css";

const local = css as Record<"grid" | "tile" | "thumb" | "sections" | "picker" | "pickerBody" | "chosen", string>;

/** « Depuis la médiathèque » (ADR-0040, lot 2): an image of Otlet chosen to be shown again. The
 * article refers to it, never copies it: its credit, licence and origin stay with the image. The
 * bank of images comes first. */
export function MediaPicker({
  workspaceId,
  onPick,
  onClose,
}: {
  workspaceId: string;
  onPick: (media: MediaEntryView) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const dialog = useRef<HTMLDialogElement>(null);
  const [section, setSection] = useState<MediaSection>("bank");
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [chosen, setChosen] = useState<MediaEntryView | null>(null);
  const list = useQuery(mediaListQuery(workspaceId, section, query, null, tag));
  const tags = useQuery(mediaTagsQuery(workspaceId));
  useEffect(() => {
    const opened = dialog.current;
    opened?.showModal();
    return () => {
      opened?.close();
    };
  }, []);
  const entries = list.data ?? [];
  return (
    <dialog
      ref={dialog}
      className={local.picker}
      aria-labelledby="media-picker-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <h2 id="media-picker-title">{t("media.picker.title")}</h2>
      <div className={local.sections} role="group" aria-label={t("media.sections")}>
        {(["bank", "articles"] as const).map((name) => (
          <button
            key={name}
            type="button"
            className={name === section ? styles.primary : styles.button}
            aria-pressed={name === section}
            onClick={() => {
              setSection(name);
              setChosen(null);
            }}
          >
            {t(`media.${name}`)}
          </button>
        ))}
      </div>
      <form
        className={styles.row}
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(typed.trim());
        }}
      >
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
      </form>
      <div className={local.pickerBody}>
        <div>
          {list.data?.length === 0 && (
            <p className={styles.help}>{query || tag ? t("media.noMatch") : t("media.picker.empty")}</p>
          )}
          <ul className={local.grid}>
            {entries.map((entry) => {
              const name = entry.name ?? t("media.unnamed");
              return (
                <li key={entry.id} className={entry.id === chosen?.id ? `${local.tile} ${styles.selected}` : local.tile}>
                  <button
                    type="button"
                    className={local.thumb}
                    aria-pressed={entry.id === chosen?.id}
                    aria-label={t("media.picker.choose", { name })}
                    onClick={() => {
                      setChosen(entry);
                    }}
                    onDoubleClick={() => {
                      onPick(entry);
                    }}
                  >
                    <img src={thumbnailUrl(workspaceId, entry.id)} alt="" loading="lazy" />
                  </button>
                  <p>{name}</p>
                </li>
              );
            })}
          </ul>
        </div>
        {chosen !== null && (
          <aside className={local.chosen} aria-label={t("media.picker.details")}>
            <img src={thumbnailUrl(workspaceId, chosen.id)} alt="" />
            <p>
              <strong>{chosen.name ?? t("media.unnamed")}</strong>
            </p>
            <p className={styles.meta}>
              {chosen.width} × {chosen.height} px · {t(`media.origins.${chosen.origin}`)}
            </p>
            {chosen.description && <p>{chosen.description}</p>}
            <dl className={styles.meta}>
              <dt>{t("media.sheet.credit")}</dt>
              <dd>{chosen.credit ?? t("media.picker.missing")}</dd>
              <dt>{t("media.sheet.licence")}</dt>
              <dd>{chosen.licence ?? t("media.picker.missing")}</dd>
              {chosen.tags.length > 0 && (
                <>
                  <dt>{t("media.tags")}</dt>
                  <dd>{chosen.tags.join(", ")}</dd>
                </>
              )}
            </dl>
          </aside>
        )}
      </div>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.primary}
          disabled={chosen === null}
          onClick={() => {
            if (chosen !== null) {
              onPick(chosen);
            }
          }}
        >
          {t("media.picker.insert")}
        </button>
        <button type="button" className={styles.button} onClick={onClose}>
          {t("media.picker.cancel")}
        </button>
      </p>
    </dialog>
  );
}
