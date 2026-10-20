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
import {
  briefQuery,
  briefsQuery,
  useDeleteBrief,
  useSaveBrief,
  vocabularyQuery,
  type BriefLength,
  type BriefMode,
  type BriefItemView,
  type BriefView,
  type ChoiceView,
  type VocabularyView,
} from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { DraftPanel } from "./DraftPanel.tsx";

const LENGTHS: readonly BriefLength[] = ["short", "medium", "long"];
const MODES: readonly BriefMode[] = ["synthesis", "panorama"];
const LANGUAGES = ["fr", "en", "de", "nl", "es", "it", "pt"] as const;
const BRIEF_ERRORS = [
  "invalid_title",
  "invalid_angle",
  "invalid_instructions",
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
            {/* Information, not an alarm (Joël, 2026-10-19): a faithful summary is a brief too. */}
            {brief.angle === "" ? (
              <p className={styles.meta}>{t("brief.angleUnset")}</p>
            ) : (
              <p className={styles.meta}>
                {t("brief.angleSet")} : {brief.angle.slice(0, 280)}
              </p>
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
  const [instructions, setInstructions] = useState(brief?.instructions ?? "");
  const [audience, setAudience] = useState(brief?.audience ?? "");
  const [tone, setTone] = useState(brief?.tone ?? "neutral");
  const vocabulary = useQuery(vocabularyQuery(workspaceId));
  const [length, setLength] = useState<BriefLength>(brief?.length ?? "medium");
  const [mode, setMode] = useState<BriefMode>(brief?.mode ?? "synthesis");
  const [language, setLanguage] = useState(brief?.language ?? "fr");
  const [channel, setChannel] = useState(brief?.channel ?? "");
  const [model, setModel] = useState(brief?.provider_id ? `${brief.provider_id}|${brief.model ?? ""}` : "");
  const [itemIds, setItemIds] = useState<string[]>(brief?.items.map((item) => item.id) ?? initialItems);
  const [confirming, setConfirming] = useState(false);
  const [autoTitle, setAutoTitle] = useState<string | null>(null);
  const channels = vocabulary.data?.channel ?? [];
  const channelMax = channels.find((choice) => choice.key === channel)?.length_max ?? "long";
  const known = useBriefItems(workspaceId, brief, itemIds);
  const matter = itemIds.reduce((sum, id) => sum + (known.get(id)?.words ?? 0), 0);
  // The length the sources can carry (Joël, 2026-10-19): the drafts hold to it as well.
  const matterMax = longestFor(matter, vocabulary.data);
  // A new brief opened from the Veille with its items: its working title is the first one's.
  const firstTitle = itemIds[0] === undefined ? undefined : known.get(itemIds[0])?.title;
  const shownTitle = brief === null && title === "" && autoTitle === null ? (firstTitle ?? "") : title;
  const lengthMax = [channelMax, matterMax ?? "short"].reduce((a, b) => (LENGTHS.indexOf(a) <= LENGTHS.indexOf(b) ? a : b));
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
                title: shownTitle,
                angle,
                instructions,
                audience,
                tone,
                length,
                mode,
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
        {/* The items first, then the title, the angle and the instructions (Joël, 2026-10-19):
            an article starts from the articles it rests on. */}
        <BriefItems
          workspaceId={workspaceId}
          brief={brief}
          itemIds={itemIds}
          onChange={(ids, first) => {
            setItemIds(ids);
            // The working title follows the first item until the author writes their own.
            const following = shownTitle.trim() === "" || shownTitle === autoTitle;
            if (first !== undefined && (following || (brief === null && autoTitle === null))) {
              setTitle(first);
              setAutoTitle(first);
            }
          }}
        />
        <div className={styles.field}>
          <label htmlFor="brief-title">{t("brief.title")}</label>
          <input
            id="brief-title"
            required
            maxLength={200}
            value={shownTitle}
            onChange={(event) => {
              setTitle(event.target.value);
              setAutoTitle((before) => before ?? shownTitle);
            }}
          />
        </div>
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
          <span className={styles.meta}>{angle.trim() === "" ? t("brief.angleUnset") : t("brief.angleSet")}</span>
        </div>
        <div className={styles.field}>
          <label htmlFor="brief-instructions">{t("brief.instructions")}</label>
          <textarea
            id="brief-instructions"
            rows={3}
            maxLength={2000}
            placeholder={t("brief.instructionsExample")}
            value={instructions}
            onChange={(event) => {
              setInstructions(event.target.value);
            }}
          />
          <span className={styles.help}>{t("brief.instructionsHelp")}</span>
        </div>
        <ChoiceField
          id="brief-audience"
          label={t("brief.audience")}
          choices={vocabulary.data?.audience ?? []}
          value={audience}
          onChange={setAudience}
        />
        <ChoiceField
          id="brief-tone"
          label={t("brief.tone")}
          choices={vocabulary.data?.tone ?? []}
          value={tone}
          onChange={setTone}
        />
        {/* With one item, the mode is not even sent to the model (Joël, 2026-10-19). */}
        {itemIds.length > 1 && (
          <div className={styles.field}>
            <label htmlFor="brief-mode">{t("brief.mode")}</label>
            <select
              id="brief-mode"
              value={mode}
              onChange={(event) => {
                setMode(MODES.find((choice) => choice === event.target.value) ?? "synthesis");
              }}
            >
              {MODES.map((choice) => (
                <option key={choice} value={choice}>
                  {t(`brief.modes.${choice}`)}
                </option>
              ))}
            </select>
            <span className={styles.help}>{t(`brief.modeHelp.${mode}`)}</span>
          </div>
        )}
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
                <option key={choice} value={choice} disabled={LENGTHS.indexOf(choice) > LENGTHS.indexOf(lengthMax)}>
                  {t(`brief.lengths.${choice}`)}
                </option>
              ))}
            </select>
            {matterMax === null ? (
              <span className={styles.help}>{t("brief.lengthMatter", { count: matter })}</span>
            ) : (
              lengthMax !== "long" && (
                <span className={styles.help}>
                  {LENGTHS.indexOf(matterMax) < LENGTHS.indexOf(channelMax)
                    ? t("brief.lengthMatter", { count: matter })
                    : t("brief.lengthCapped")}
                </span>
              )
            )}
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
        <ChoiceField
          id="brief-channel"
          label={t("brief.channel")}
          choices={channels}
          value={channel}
          onChange={(key) => {
            setChannel(key);
            // A channel that cannot carry a longer article brings the length down (Joël, 2026-10-19).
            const max = channels.find((choice) => choice.key === key)?.length_max ?? "long";
            if (LENGTHS.indexOf(length) > LENGTHS.indexOf(max)) {
              setLength(max);
            }
          }}
        />
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
      {brief !== null && <DraftPanel workspaceId={workspaceId} briefId={brief.id} />}
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
/** The items of the form: those of the saved brief, and those added since, fetched. */
function useBriefItems(workspaceId: string, brief: BriefView | null, itemIds: string[]): Map<string, BriefItemView> {
  const known = new Map((brief?.items ?? []).map((item) => [item.id, item]));
  const missing = itemIds.filter((id) => !known.has(id));
  const fetched = useQueries({ queries: missing.map((id) => itemQuery(workspaceId, id)) });
  for (const result of fetched) {
    if (result.data !== undefined) {
      const item = result.data;
      // The words a draft may use, as the drafts count them: the text Otlet may use, else the summary.
      const text = item.text ?? item.summary ?? item.title;
      known.set(item.id, {
        id: item.id,
        title: item.title,
        url: item.url,
        source_id: item.source_id,
        source_name: item.source_name,
        published_at: item.published_at,
        words: text.trim() === "" ? 0 : text.trim().split(/\s+/).length,
        full_text: item.text !== null,
        declared: item.text_reason === "declared_rights",
      });
    }
  }
  return known;
}

/** How much the sources hold (draft.py, matter_level): nothing said, a notice, or a warning. */
function matterLevel(
  matter: number,
  fullText: boolean,
  vocabulary: VocabularyView | undefined,
): "enough" | "limited" | "insufficient" {
  if (vocabulary === undefined) {
    return "enough";
  }
  const longest = longestFor(matter, vocabulary);
  if (matter < vocabulary.matter_floor || (!fullText && longest === null)) {
    return "insufficient";
  }
  return longest === null ? "limited" : "enough";
}

/** The longest article the words of the sources can carry (draft.py, longest_for); null: thin. */
function longestFor(matter: number, vocabulary: VocabularyView | undefined): BriefLength | null {
  if (vocabulary === undefined) {
    return "long";
  }
  const fitting = LENGTHS.filter((length) => (vocabulary.length_words[length] ?? 0) <= matter * vocabulary.matter_share);
  return fitting.at(-1) ?? null;
}

// One line of the items: its list takes the room left by its words and its buttons.
const LINE = { display: "flex", gap: "0.5rem", alignItems: "center", width: "100%" } as const;

function BriefItems({
  workspaceId,
  brief,
  itemIds,
  onChange,
}: {
  workspaceId: string;
  brief: BriefView | null;
  itemIds: string[];
  // `firstTitle`: the title of the first item, when it changed (the working title follows it).
  onChange: (ids: string[], firstTitle?: string) => void;
}) {
  const { t } = useTranslation();
  const known = useBriefItems(workspaceId, brief, itemIds);
  const matter = itemIds.reduce((sum, id) => sum + (known.get(id)?.words ?? 0), 0);
  const vocabulary = useQuery(vocabularyQuery(workspaceId));
  const level = matterLevel(
    matter,
    itemIds.some((id) => known.get(id)?.full_text === true),
    vocabulary.data,
  );
  // The kept items, the most recent first (by date of publication).
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
  // An empty line waiting for its item: « + » adds one (Joël, 2026-10-19).
  const [empty, setEmpty] = useState(itemIds.length === 0);
  // Always one line at least: removing the last item leaves an empty one (Joël, 2026-10-19).
  const rows = empty || itemIds.length === 0 ? [...itemIds, ""] : itemIds;
  const sources = new Set(itemIds.map((id) => known.get(id)?.source_id ?? id));
  const label = (title: string, source: string | null, words: number): string =>
    `${title.length > 90 ? `${title.slice(0, 89)}…` : title} · ${source ?? t("watch.manualOrigin")} · ${t("watch.words", { count: words })}`;
  const choose = (index: number, id: string) => {
    const next = [...rows];
    next[index] = id;
    const ids = next.filter((other) => other !== "");
    setEmpty(false);
    const firstChanged = ids[0] !== undefined && ids[0] !== itemIds[0];
    const first = ids[0] === undefined ? undefined : (kept.data?.find((e) => e.item.id === ids[0])?.item.title ?? known.get(ids[0])?.title);
    onChange(ids, firstChanged ? first : undefined);
  };
  return (
    // A fieldset grows to its widest content by default: a long title would widen the page.
    <fieldset className={styles.choices} style={{ minWidth: 0 }}>
      <legend>{t("brief.items", { count: itemIds.length })}</legend>
      {rows.map((id, index) => {
        const item = id === "" ? undefined : known.get(id);
        // Its own item, then the kept items no other line holds.
        const offered = (kept.data ?? []).filter((entry) => entry.item.id === id || !itemIds.includes(entry.item.id));
        const listed = id !== "" && !offered.some((entry) => entry.item.id === id);
        return (
          <div key={`${String(index)}-${id}`} style={LINE}>
            <select
              style={{ flex: "1 1 0", minWidth: 0 }}
              aria-label={t("brief.itemLine", { number: index + 1 })}
              value={id}
              onChange={(event) => {
                choose(index, event.target.value);
              }}
            >
              <option value="">{t("brief.pickItem")}</option>
              {listed && item !== undefined && (
                <option value={id}>{label(item.title, item.source_name, item.words)}</option>
              )}
              {offered.map((entry) => (
                <option key={entry.item.id} value={entry.item.id}>
                  {label(entry.item.title, entry.item.source_name, entry.item.words)}
                </option>
              ))}
            </select>
            {item !== undefined && (
              <Link
                to="/veille/elements/$itemId"
                params={{ itemId: id }}
                className={styles.meta}
                style={{ whiteSpace: "nowrap" }}
              >
                {item.full_text ? t("brief.words", { count: item.words }) : t("brief.summaryOnly", { count: item.words })}
                {item.declared && ` · ${t("text.declared")}`}
              </Link>
            )}
            {(id !== "" || rows.length > 1) && (
              <button
                type="button"
                className={styles.button}
                aria-label={t("brief.removeItem", { title: item?.title ?? "" })}
                onClick={() => {
                  if (id === "") {
                    setEmpty(false);
                    return;
                  }
                  const ids = itemIds.filter((other) => other !== id);
                  const first = ids[0] === undefined ? undefined : known.get(ids[0])?.title;
                  onChange(ids, ids[0] !== itemIds[0] ? first : undefined);
                }}
              >
                ×
              </button>
            )}
            {index === rows.length - 1 && id !== "" && (
              <button
                type="button"
                className={styles.button}
                aria-label={t("brief.addLine")}
                onClick={() => {
                  setEmpty(true);
                }}
              >
                +
              </button>
            )}
          </div>
        );
      })}
      <div style={{ width: "100%" }}>
      {itemIds.length === 0 && (kept.data ?? []).length === 0 && <p className={styles.meta}>{t("brief.noKept")}</p>}
      {itemIds.length > 0 && sources.size < 2 && <p className={styles.notice}>{t("brief.singleSource")}</p>}
      {itemIds.length > 0 && <p className={styles.meta}>{t("brief.matter", { count: matter })}</p>}
      {itemIds.length > 0 && level === "limited" && <p className={styles.notice}>{t("brief.matterLimited")}</p>}
      {itemIds.length > 0 && level === "insufficient" && <p className={styles.warning}>{t("brief.matterInsufficient")}</p>}
      </div>
    </fieldset>
  );
}

/** The model of the brief: the profile of Réglages > IA, or one model of one provider. The
 * models offered are those of Mon profil: installed on a local engine, listed by the catalogue
 * for the others. */
/** A closed list of the brief (audience, tone, channel), with the definition the model receives. */
function ChoiceField({
  id,
  label,
  choices,
  value,
  onChange,
}: {
  id: string;
  label: string;
  choices: ChoiceView[];
  value: string;
  onChange: (key: string) => void;
}) {
  const { t } = useTranslation();
  const chosen = choices.find((choice) => choice.key === value);
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        <option value="">{t("brief.unspecified")}</option>
        {choices.map((choice) => (
          <option key={choice.key} value={choice.key}>
            {choice.label}
          </option>
        ))}
      </select>
      {chosen !== undefined && <span className={styles.help}>{chosen.definition}</span>}
    </div>
  );
}

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
