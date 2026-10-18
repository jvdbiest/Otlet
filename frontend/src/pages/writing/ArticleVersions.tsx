// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { toDocument } from "../../editor/document.ts";
import { mediaUrl } from "../../media.ts";
import { useSaveVersion, useSendArticle, type ArticleView, type VersionView } from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { blockAnchor, findBlock } from "./blocks.ts";
import { DocumentView, type PlatformDocument } from "./DocumentView.tsx";
import { ExportTools } from "./ExportTools.tsx";
import { GenerationDetails } from "./GenerationDetails.tsx";
import { VersionEditor } from "./VersionEditor.tsx";
import { Warning } from "./Warning.tsx";

/** A list of the details: the sections of a synthesis still on one source, the paragraphs
 * that repeat another. */
function listed(details: Record<string, unknown>, key: "lone_sections" | "repeated_paragraphs"): string[] {
  const found = details[key];
  return Array.isArray(found) ? found.filter((h): h is string => typeof h === "string") : [];
}

/** The versions of an article (U04, X03, X04): read one, edit it with the editor of Otlet, export
 * it. The same in the brief (the workshop) and in the Library. `chosen` is the version shown, the
 * latest when null. */
export function ArticleVersions({
  workspaceId,
  article,
  chosen,
  onChoose,
  actions,
}: {
  workspaceId: string;
  article: ArticleView;
  chosen: number | null;
  onChoose: (number: number | null) => void;
  actions?: (shown: VersionView) => ReactNode;
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  // « Modifier » on a model's version first makes the person's copy (Joël, 2026-10-18).
  const [copiedFrom, setCopiedFrom] = useState<number | null>(null);
  const copy = useSaveVersion(workspaceId);
  const send = useSendArticle(workspaceId);
  const [forked, setForked] = useState<{ from: number; to: number } | null>(null);
  const versions = article.versions;
  const shown = versions.find((v) => v.number === chosen) ?? versions.at(-1);
  if (shown === undefined) {
    return null;
  }
  const prefix = `v${String(shown.number)}`;
  const lone = listed(shown.details, "lone_sections");
  const repeated = listed(shown.details, "repeated_paragraphs");
  const anchor = (type: string, start: string, skip = 0): string | undefined => {
    const id = findBlock(shown.document as unknown as PlatformDocument, type, start, skip);
    return id === undefined ? undefined : blockAnchor(prefix, id);
  };
  return (
    <>
      <div className={styles.row}>
        {versions.length > 1 && (
          <select
            aria-label={t("draft.version")}
            disabled={editing}
            value={shown.number}
            onChange={(event) => {
              onChoose(Number(event.target.value));
            }}
          >
            {versions.map((v) => (
              <option key={v.number} value={v.number}>
                {t("draft.versionLabel", {
                  number: v.number,
                  who: t(`draft.who.${v.origin}`),
                  date: formatDate(v.updated_at),
                })}
                {v.number === article.validated_version ? t("library.validatedMark") : ""}
              </option>
            ))}
          </select>
        )}
        <span className={styles.meta}>
          {shown.origin === "ia"
            ? t("draft.byModel", {
                number: shown.number,
                model: shown.model ?? "",
                provider: shown.provider_kind ?? "",
                date: formatDate(shown.created_at),
              })
            : t("draft.byPerson", {
                number: shown.number,
                based: shown.based_on ?? "?",
                date: formatDate(shown.updated_at),
              })}
        </span>
      </div>
      {shown.context_overflow && <Warning text={t("draft.overflow")} />}
      {shown.unused_sources.length > 0 && (
        <Warning
          text={t("draft.unused", { count: shown.unused_sources.length })}
          items={shown.unused_sources.map((title) => ({ label: title }))}
        />
      )}
      {lone.length > 0 && (
        <Warning
          text={t("draft.lone", { count: lone.length })}
          items={lone.map((heading) => ({ label: heading, anchor: anchor("heading", heading) }))}
        />
      )}
      {repeated.length > 0 && (
        <Warning
          text={t("draft.repeated", { count: repeated.length })}
          items={repeated.map((start, index) => ({
            label: start,
            // The copy, not the paragraph it repeats: skip that one and the earlier copies.
            anchor: anchor("paragraph", start, 1 + repeated.slice(0, index).filter((s) => s === start).length),
          }))}
        />
      )}
      {shown.cut_sources.length > 0 && (
        <p className={styles.notice}>{t("draft.cut", { sources: shown.cut_sources.join(", ") })}</p>
      )}
      {shown.origin === "ia" && (
        <GenerationDetails
          details={shown.details}
          heading={t("draft.details.heading", { number: shown.number, date: formatDate(shown.created_at) })}
        />
      )}
      {forked !== null && article.validated_version === forked.from && (
        <div role="note" className={styles.warning}>
          <p>{t("library.forked", { from: forked.from, to: forked.to })}</p>
          <p className={styles.row}>
            <button
              type="button"
              className={styles.primary}
              disabled={send.isPending}
              onClick={() => {
                send.mutate(
                  { articleId: article.id, number: forked.to },
                  {
                    onSuccess: () => {
                      setForked(null);
                    },
                  },
                );
              }}
            >
              {t("library.validateThis", { number: forked.to })}
            </button>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setForked(null);
              }}
            >
              {t("library.keepValidated", { number: forked.from })}
            </button>
          </p>
        </div>
      )}
      {editing ? (
        <VersionEditor
          key={`${article.id}-${String(shown.number)}`}
          workspaceId={workspaceId}
          articleId={article.id}
          version={shown}
          onSaved={(number, from) => {
            // A retouch of the validated version made a new one (Joël, 2026-10-18): ask once.
            if (from === article.validated_version && number !== from) {
              setForked({ from, to: number });
            }
            onChoose(number);
          }}
          copiedFrom={copiedFrom}
          validated={article.validated_version}
          onClose={() => {
            setEditing(false);
            setCopiedFrom(null);
          }}
        />
      ) : (
        <>
          <p className={styles.row}>
            <button
              type="button"
              className={styles.button}
              disabled={copy.isPending}
              onClick={() => {
                if (shown.origin !== "ia") {
                  // Pinned: a draft generated meanwhile must not replace the text being edited.
                  onChoose(shown.number);
                  setEditing(true);
                  return;
                }
                const attrs = shown.document.attrs as Record<string, unknown>;
                copy.mutate(
                  {
                    articleId: article.id,
                    number: shown.number,
                    body: {
                      title: shown.title,
                      document: toDocument(shown.document, attrs),
                      updated_at: shown.updated_at,
                      as_new: true,
                    },
                  },
                  {
                    onSuccess: (made) => {
                      setCopiedFrom(shown.number);
                      onChoose(made.number);
                      setEditing(true);
                    },
                  },
                );
              }}
            >
              {t("draft.edit")}
            </button>
            <ExportTools workspaceId={workspaceId} articleId={article.id} number={shown.number} />
            {actions?.(shown)}
          </p>
          {copy.error !== null && (
            <p role="alert" className={styles.error}>
              {errorText(t, copy.error)}
            </p>
          )}
          <DocumentView
            document={shown.document as unknown as PlatformDocument}
            title={shown.title}
            prefix={prefix}
            mediaUrl={(id) => mediaUrl(workspaceId, id)}
          />
        </>
      )}
    </>
  );
}
