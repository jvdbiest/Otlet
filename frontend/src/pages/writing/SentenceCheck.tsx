// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState, type MouseEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api, apiError, type components } from "../../api/client.ts";
import { errorText } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import type { PlatformDocument } from "./DocumentView.tsx";

type SupportView = components["schemas"]["SupportView"];
interface Checked {
  text: string;
  sources: { key: string; title: string }[];
}

const SENTENCE = /[^.!?…]+[.!?…]*\s*/g;
const REFERENCE = /\s*\[\d+\]/g;

/** The sentence of a paragraph the author clicked in, without its references [n]. */
function clickedSentence(paragraph: HTMLElement): string | null {
  const selection = window.getSelection();
  if (selection?.anchorNode == null || !paragraph.contains(selection.anchorNode)) {
    return null;
  }
  const chosen = selection.toString().trim();
  if (chosen.length >= 15) {
    return chosen.replace(REFERENCE, "");
  }
  const before = document.createRange();
  before.setStart(paragraph, 0);
  before.setEnd(selection.anchorNode, selection.anchorOffset);
  const at = before.toString().length;
  const text = paragraph.textContent;
  for (const match of text.matchAll(SENTENCE)) {
    if (at >= match.index && at <= match.index + match[0].length) {
      const sentence = match[0].replace(REFERENCE, "").trim();
      return sentence.length >= 15 ? sentence : null;
    }
  }
  return null;
}

/** The names and figures shared with the sentence checked, marked in a source sentence. */
function highlighted(sentence: string, shared: string[]): ReactNode {
  if (shared.length === 0) {
    return sentence;
  }
  const escaped = shared.map((s) => s.normalize("NFD").replace(/\p{M}/gu, "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const bare = sentence.normalize("NFD").replace(/\p{M}/gu, "");
  const pattern = new RegExp(escaped.join("|"), "giu");
  const parts: ReactNode[] = [];
  let at = 0;
  // Positions found on the text without accents fall on the same characters: one mark each.
  for (const match of bare.matchAll(pattern)) {
    parts.push(sentence.slice(at, match.index), <mark key={match.index}>{sentence.slice(match.index, match.index + match[0].length)}</mark>);
    at = match.index + match[0].length;
  }
  parts.push(sentence.slice(at));
  return parts;
}

/** The reading aid of REL2 (Joël, 2026-11-08): a click on a sentence of the version shows the
 * sentences of the sources its paragraph cites that share the most with it, its names and
 * figures marked. No model: the author sees what confirms or contradicts, and judges. */
export function SentenceCheck({
  workspaceId,
  briefId,
  document: platform,
  children,
}: {
  workspaceId: string;
  briefId: string | null;
  document: PlatformDocument;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [checked, setChecked] = useState<Checked | null>(null);
  const support = useQuery({
    queryKey: ["workspaces", workspaceId, "briefs", briefId, "support", checked],
    enabled: briefId !== null && checked !== null,
    queryFn: async (): Promise<SupportView[]> => {
      const { data, error, response } = await api.POST("/api/workspaces/{workspace_id}/briefs/{brief_id}/support", {
        params: { path: { workspace_id: workspaceId, brief_id: briefId ?? "" } },
        body: checked ?? { text: "", sources: [] },
      });
      if (data === undefined) {
        throw apiError(response, error);
      }
      return data;
    },
  });
  if (briefId === null) {
    return <>{children}</>;
  }
  const titles = new Map(platform.attrs.sources.map((source) => [source.id, source.titre]));
  const numbers = new Map(platform.attrs.sources.map((source, index) => [source.id, index + 1]));
  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest("a") !== null) {
      return; // a reference or a link keeps its own behaviour
    }
    const paragraph = target.closest("p");
    if (paragraph === null || !event.currentTarget.contains(paragraph)) {
      return;
    }
    const text = clickedSentence(paragraph);
    if (text === null) {
      return;
    }
    const keys = [...paragraph.querySelectorAll<HTMLElement>("a.otlet-source-ref")]
      .map((ref) => ref.dataset.source ?? "")
      .filter((key, n, all) => key !== "" && all.indexOf(key) === n);
    setChecked({ text, sources: keys.map((key) => ({ key, title: titles.get(key) ?? "" })) });
  };
  return (
    <div onClick={onClick}>
      <p className={styles.help}>{t("check.hint")}</p>
      {children}
      {checked !== null && (
        <aside
          className={styles.card}
          aria-label={t("check.title")}
          style={{
            position: "fixed",
            right: "1rem",
            bottom: "1rem",
            width: "min(40rem, 92vw)",
            maxHeight: "50vh",
            overflowY: "auto",
            zIndex: 20,
            background: "var(--surface, Canvas)",
          }}
          onClick={(event) => {
            event.stopPropagation();
          }}
        >
          <p className={styles.row}>
            <strong>{t("check.title")}</strong>
            <button
              type="button"
              className={styles.button}
              onClick={() => {
                setChecked(null);
              }}
            >
              {t("check.close")}
            </button>
          </p>
          <p className={styles.meta}>« {checked.text} »</p>
          {support.isPending && <p>{t("app.loading")}</p>}
          {support.error !== null && <p role="alert">{errorText(t, support.error)}</p>}
          {support.data?.length === 0 && <p className={styles.notice}>{t("check.nothing")}</p>}
          {support.data !== undefined && support.data.length > 0 && (
            <ol>
              {support.data.map((found, n) => (
                <li key={`${found.key}-${String(n)}`} style={{ marginBottom: "0.5rem" }}>
                  <span>{highlighted(found.sentence, found.shared)}</span>
                  <br />
                  <span className={styles.meta}>
                    {numbers.has(found.key) ? `[${String(numbers.get(found.key))}] ` : ""}
                    {found.title}
                    {found.publisher ? ` · ${found.publisher}` : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <p className={styles.help}>{t("check.help")}</p>
        </aside>
      )}
    </div>
  );
}
