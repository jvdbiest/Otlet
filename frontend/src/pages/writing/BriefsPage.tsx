// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { catalogueQuery, installedQuery, profileQuery, providersQuery } from "../../ai.ts";
import { ApiError } from "../../api/client.ts";
import { itemQuery } from "../../collection.ts";
import { useWorkspaceId } from "../../session.ts";
import { feedQuery, ANY_TIME } from "../../triage.ts";
import { briefQuery, briefsQuery, useDeleteBrief, useSaveBrief, type BriefLength, type BriefView } from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

const LENGTHS: readonly BriefLength[] = ["short", "medium", "long"];
const LANGUAGES = ["fr", "en", "de", "nl", "es", "it", "pt"] as const;
const BRIEF_ERRORS = [
  "invalid_title",
  "invalid_angle",
  "invalid_audience",
  "invalid_tone",
  "invalid_channel",
  "invalid_language",
  "invalid_items",
  "invalid_model",
  "unknown_item",
  "unknown_provider",
  "unknown_model",
  "model_blocked",
] as const;

/** The briefs of the workspace (U03): the instructions of an article, built on kept items. */
export function BriefsPage() {
  const workspaceId = useWorkspaceId();
  const { t } = useTranslation();
  const briefs = useQuery({ ...briefsQuery(workspaceId ?? ""), enabled: workspaceId !== undefined });
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{t("pages.writing.title")}</h1>
      <p className={styles.help}>{t("brief.intro")}</p>
      <p>
        <Link to="/redaction/nouveau" search={{ items: "" }} className={styles.primary}>
          {t("brief.new")}
        </Link>
      </p>
      {briefs.isError && <p role="alert">{t("watch.loadFailed")}</p>}
      {briefs.data?.length === 0 && <p className={styles.meta}>{t("brief.empty")}</p>}
      <ul className={styles.list}>
        {(briefs.data ?? []).map((brief) => (
          <li key={brief.id} className={styles.card}>
            <h2>
              <Link to="/redaction/briefs/$briefId" params={{ briefId: brief.id }}>
                {brief.title}
              </Link>
            </h2>
            <p className={styles.meta}>
              {t("brief.summary", { items: brief.items.length, sources: brief.sources })} ·{" "}
              {t("brief.changed", { date: formatDate(brief.updated_at) })}
            </p>
            {brief.angle === "" ? (
              <p className={styles.warning}>{t("brief.noAngle")}</p>
            ) : (
              <p className={styles.meta}>{brief.angle.slice(0, 280)}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A new brief, on the items chosen in the watch (`items`, comma separated ids). */
export function NewBriefPage({ items }: { items: string }) {
  const workspaceId = useWorkspaceId();
  if (workspaceId === undefined) {
    return null;
  }
  const ids = items.split(",").filter((id) => id !== "");
  return <BriefForm workspaceId={workspaceId} brief={null} initialItems={ids} />;
}

export function BriefPage({ briefId }: { briefId: string }) {
  const workspaceId = useWorkspaceId();
  const { t } = useTranslation();
  const brief = useQuery({ ...briefQuery(workspaceId ?? "", briefId), enabled: workspaceId !== undefined });
  if (workspaceId === undefined) {
    return null;
  }
  if (brief.isError) {
    return <p role="alert">{t("brief.notFound")}</p>;
  }
  if (brief.data === undefined) {
    return <p>{t("app.loading")}</p>;
  }
  return <BriefForm key={brief.data.id} workspaceId={workspaceId} brief={brief.data} initialItems={[]} />;
}

function briefError(t: Parameters<typeof errorText>[0], error: Error): string {
  if (error instanceof ApiError && error.detail !== null) {
    const code = BRIEF_ERRORS.find((known) => known === error.detail);
    if (code !== undefined) {
      return t(`brief.errors.${code}`);
    }
  }
  return errorText(t, error);
}

function BriefForm({
  workspaceId,
  brief,
  initialItems,
}: {
  workspaceId: string;
  brief: BriefView | null;
  initialItems: string[];
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const save = useSaveBrief(workspaceId);
  const remove = useDeleteBrief(workspaceId);
  const [title, setTitle] = useState(brief?.title ?? "");
  const [angle, setAngle] = useState(brief?.angle ?? "");
  const [audience, setAudience] = useState(brief?.audience ?? "");
  const [tone, setTone] = useState(brief?.tone ?? "");
  const [length, setLength] = useState<BriefLength>(brief?.length ?? "medium");
  const [language, setLanguage] = useState(brief?.language ?? "fr");
  const [channel, setChannel] = useState(brief?.channel ?? "");
  const [model, setModel] = useState(brief?.provider_id ? `${brief.provider_id}|${brief.model ?? ""}` : "");
  const [itemIds, setItemIds] = useState<string[]>(brief?.items.map((item) => item.id) ?? initialItems);
  const [confirming, setConfirming] = useState(false);
  return (
    <section aria-labelledby="page-title">
      <p>
        <Link to="/redaction">{t("brief.back")}</Link>
      </p>
      <h1 id="page-title">{brief === null ? t("brief.new") : brief.title}</h1>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          const [providerId, modelName] = model === "" ? [null, null] : model.split("|", 2);
          save.mutate(
            {
              briefId: brief?.id ?? null,
              body: {
                title,
                angle,
                audience,
                tone,
                length,
                language,
                channel,
                item_ids: itemIds,
                provider_id: providerId ?? null,
                model: modelName ?? null,
              },
            },
            {
              onSuccess: (saved) => {
                if (brief === null) {
                  void navigate({ to: "/redaction/briefs/$briefId", params: { briefId: saved.id } });
                }
              },
            },
          );
        }}
      >
        <div className={styles.field}>
          <label htmlFor="brief-angle">{t("brief.angle")}</label>
          <textarea
            id="brief-angle"
            rows={5}
            maxLength={4000}
            placeholder={t("brief.angleExample")}
            value={angle}
            onChange={(event) => {
              setAngle(event.target.value);
            }}
          />
          <span className={styles.help}>{t("brief.angleHelp")}</span>
          {angle.trim() === "" && <span className={styles.warning}>{t("brief.noAngle")}</span>}
        </div>
        <div className={styles.field}>
          <label htmlFor="brief-title">{t("brief.title")}</label>
          <input
            id="brief-title"
            required
            maxLength={200}
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        </div>
        <BriefItems workspaceId={workspaceId} brief={brief} itemIds={itemIds} onChange={setItemIds} />
        <div className={styles.field}>
          <label htmlFor="brief-audience">{t("brief.audience")}</label>
          <input
            id="brief-audience"
            maxLength={200}
            value={audience}
            onChange={(event) => {
              setAudience(event.target.value);
            }}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="brief-tone">{t("brief.tone")}</label>
          <input
            id="brief-tone"
            maxLength={200}
            value={tone}
            onChange={(event) => {
              setTone(event.target.value);
            }}
          />
        </div>
        <div className={styles.search}>
          <div className={styles.field}>
            <label htmlFor="brief-length">{t("brief.length")}</label>
            <select
              id="brief-length"
              value={length}
              onChange={(event) => {
                setLength(LENGTHS.find((choice) => choice === event.target.value) ?? "medium");
              }}
            >
              {LENGTHS.map((choice) => (
                <option key={choice} value={choice}>
                  {t(`brief.lengths.${choice}`)}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="brief-language">{t("brief.language")}</label>
            <select
              id="brief-language"
              value={language}
              onChange={(event) => {
                setLanguage(event.target.value);
              }}
            >
              {LANGUAGES.map((code) => (
                <option key={code} value={code}>
                  {t(`topics.languageNames.${code}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className={styles.field}>
          <label htmlFor="brief-channel">{t("brief.channel")}</label>
          <input
            id="brief-channel"
            maxLength={200}
            value={channel}
            onChange={(event) => {
              setChannel(event.target.value);
            }}
          />
        </div>
        <ModelSelect value={model} onChange={setModel} />
        {save.error !== null && (
          <p role="alert" className={styles.error}>
            {briefError(t, save.error)}
          </p>
        )}
        <p className={styles.row}>
          <button type="submit" className={styles.primary} disabled={save.isPending || itemIds.length === 0}>
            {brief === null ? t("brief.create") : t("brief.save")}
          </button>
          {save.isSuccess && brief !== null && <span className={styles.meta}>{t("brief.saved")}</span>}
        </p>
      </form>
      {brief !== null && (
        <div className={styles.dangerZone}>
          {confirming ? (
            <p className={styles.row}>
              <span>{t("brief.confirmDelete")}</span>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  remove.mutate(brief.id, {
                    onSuccess: () => {
                      void navigate({ to: "/redaction" });
                    },
                  });
                }}
              >
                {t("brief.confirm")}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  setConfirming(false);
                }}
              >
                {t("brief.cancel")}
              </button>
            </p>
          ) : (
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setConfirming(true);
              }}
            >
              {t("brief.delete")}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/** The items of the brief, and the kept items that can be added to it. */
function BriefItems({
  workspaceId,
  brief,
  itemIds,
  onChange,
}: {
  workspaceId: string;
  brief: BriefView | null;
  itemIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const { t } = useTranslation();
  const known = new Map((brief?.items ?? []).map((item) => [item.id, item]));
  const missing = itemIds.filter((id) => !known.has(id));
  const fetched = useQueries({ queries: missing.map((id) => itemQuery(workspaceId, id)) });
  for (const result of fetched) {
    if (result.data !== undefined) {
      const item = result.data;
      known.set(item.id, {
        id: item.id,
        title: item.title,
        url: item.url,
        source_id: item.source_id,
        source_name: item.source_name,
        published_at: item.published_at,
      });
    }
  }
  const kept = useQuery(
    feedQuery(
      workspaceId,
      {
        view: "kept",
        sourceId: null,
        unread: false,
        topicIds: [],
        allTopics: false,
        period: ANY_TIME,
        sort: "date",
        group: null,
      },
      null,
    ),
  );
  const sources = new Set(itemIds.map((id) => known.get(id)?.source_id ?? id));
  const addable = (kept.data ?? []).filter((entry) => !itemIds.includes(entry.item.id));
  return (
    <fieldset className={styles.choices}>
      <legend>{t("brief.items", { count: itemIds.length })}</legend>
      {itemIds.length === 0 && <p className={styles.meta}>{t("brief.noItems")}</p>}
      <ol className={styles.list}>
        {itemIds.map((id) => {
          const item = known.get(id);
          return (
            <li key={id} className={styles.pick}>
              <span>
                <Link to="/veille/elements/$itemId" params={{ itemId: id }}>
                  {item?.title ?? t("app.loading")}
                </Link>{" "}
                <span className={styles.meta}>{item?.source_name ?? t("watch.manualOrigin")}</span>
              </span>
              <button
                type="button"
                className={styles.button}
                aria-label={t("brief.removeItem", { title: item?.title ?? "" })}
                onClick={() => {
                  onChange(itemIds.filter((other) => other !== id));
                }}
              >
                ×
              </button>
            </li>
          );
        })}
      </ol>
      {itemIds.length > 0 && sources.size < 2 && <p className={styles.notice}>{t("brief.singleSource")}</p>}
      {addable.length > 0 && (
        <details>
          <summary>{t("brief.addKept", { count: addable.length })}</summary>
          <ul className={styles.list}>
            {addable.map((entry) => (
              <li key={entry.item.id} className={styles.pick}>
                <button
                  type="button"
                  className={styles.button}
                  aria-label={t("brief.addItem", { title: entry.item.title })}
                  onClick={() => {
                    onChange([...itemIds, entry.item.id]);
                  }}
                >
                  +
                </button>
                <span>
                  {entry.item.title}{" "}
                  <span className={styles.meta}>{entry.item.source_name ?? t("watch.manualOrigin")}</span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </fieldset>
  );
}

/** The model of the brief: the profile of Réglages > IA, or one model of one provider. The
 * models offered are those of Mon profil: installed on a local engine, listed by the catalogue
 * for the others. */
function ModelSelect({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  const providers = useQuery(providersQuery);
  const profile = useQuery(profileQuery);
  const catalogue = useQuery(catalogueQuery);
  const local = (providers.data ?? []).filter(
    (provider) => catalogue.data?.kinds.find((kind) => kind.name === provider.kind)?.custom_models === true,
  );
  const installed = useQueries({ queries: local.map((provider) => installedQuery(provider.id)) });
  const options: { value: string; label: string }[] = [];
  for (const provider of providers.data ?? []) {
    const engine = installed[local.findIndex((other) => other.id === provider.id)]?.data;
    const models = new Set(
      engine !== undefined
        ? engine.models.map((model) => model.name)
        : (catalogue.data?.models ?? [])
            .filter((model) => model.provider === provider.kind && model.status !== "blocked")
            .map((model) => model.model),
    );
    for (const entry of profile.data?.entries ?? []) {
      if (entry.provider_id === provider.id) {
        models.add(entry.model);
      }
    }
    for (const model of models) {
      options.push({ value: `${provider.id}|${model}`, label: `${provider.name} · ${model}` });
    }
  }
  if (value !== "" && !options.some((option) => option.value === value)) {
    options.push({ value, label: value.split("|", 2)[1] ?? value });
  }
  return (
    <div className={styles.field}>
      <label htmlFor="brief-model">{t("brief.model")}</label>
      <select
        id="brief-model"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        <option value="">{t("brief.profile")}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <span className={styles.help}>{t("brief.modelHelp")}</span>
    </div>
  );
}
