// SPDX-License-Identifier: AGPL-3.0-or-later
// « Comparer » (Joël, 2026-10-20): beside the draft, or beside the editor, a reference read only:
// the sources of the brief, combined or one by one, or another version. Two columns on a wide
// screen, their scrolling bound or not (🔗); two tabs on a narrow one.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { mediaUrl } from "../../media.ts";
import { briefSourcesQuery, type SourceTextView, type VersionView } from "../../writing.ts";
import { formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { DocumentView, type PlatformDocument } from "./DocumentView.tsx";

const WIDE = "(min-width: 1000px)";

function useWide(): boolean {
  return useSyncExternalStore(
    (changed) => {
      const query = window.matchMedia(WIDE);
      query.addEventListener("change", changed);
      return () => {
        query.removeEventListener("change", changed);
      };
    },
    () => window.matchMedia(WIDE).matches,
    () => true,
  );
}

/** The draft (or the editor) and, when comparing, the reference beside it. */
export function CompareLayout({
  comparing,
  reference,
  children,
}: {
  comparing: boolean;
  reference: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const wide = useWide();
  const [bound, setBound] = useState(true);
  const [tab, setTab] = useState<"draft" | "reference">("draft");
  const left = useRef<HTMLDivElement>(null);
  const right = useRef<HTMLDivElement>(null);
  const following = useRef(false);
  // Two columns need more than the reading width of the page: they take the room to its right.
  const grid = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState<number | null>(null);
  useEffect(() => {
    const measure = () => {
      const left = grid.current?.getBoundingClientRect().left;
      setWidth(left === undefined ? null : Math.max(window.innerWidth - left - 32, 0));
    };
    if (!comparing || !wide) {
      return;
    }
    measure();
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
    };
  }, [comparing, wide]);
  // The scroll of one column takes the other to the same share of its height.
  useEffect(() => {
    const a = left.current;
    const b = right.current;
    if (!comparing || !wide || !bound || a === null || b === null) {
      return;
    }
    const follow = (from: HTMLElement, to: HTMLElement) => () => {
      if (following.current) {
        following.current = false;
        return;
      }
      const share = from.scrollTop / Math.max(from.scrollHeight - from.clientHeight, 1);
      const target = share * Math.max(to.scrollHeight - to.clientHeight, 0);
      if (Math.abs(to.scrollTop - target) > 1) {
        following.current = true; // the scroll it causes is not followed back
        to.scrollTop = target;
      }
    };
    const fromA = follow(a, b);
    const fromB = follow(b, a);
    a.addEventListener("scroll", fromA);
    b.addEventListener("scroll", fromB);
    return () => {
      a.removeEventListener("scroll", fromA);
      b.removeEventListener("scroll", fromB);
    };
  }, [comparing, wide, bound]);
  if (!comparing) {
    return <>{children}</>;
  }
  if (!wide) {
    // A narrow screen: two tabs; both stay mounted, so the editor keeps its text.
    return (
      <>
        <p className={styles.row} role="tablist">
          {(["draft", "reference"] as const).map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={tab === name}
              className={tab === name ? styles.primary : styles.button}
              onClick={() => {
                setTab(name);
              }}
            >
              {t(`compare.tabs.${name}`)}
            </button>
          ))}
        </p>
        <div hidden={tab !== "draft"}>{children}</div>
        <div hidden={tab !== "reference"}>{reference}</div>
      </>
    );
  }
  const column = { maxHeight: "calc(100vh - 7rem)", overflowY: "auto", minWidth: 0 } as const;
  return (
    <>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.button}
          aria-pressed={bound}
          title={bound ? t("compare.unbind") : t("compare.bind")}
          onClick={() => {
            setBound(!bound);
          }}
        >
          {bound ? "🔗" : "⛓️‍💥"} {bound ? t("compare.bound") : t("compare.free")}
        </button>
      </p>
      <div
        ref={grid}
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
          gap: "1.5rem",
          alignItems: "start",
          width: width === null ? "100%" : `${String(Math.max(width, 0))}px`,
          maxWidth: "1800px",
        }}
      >
        <div ref={left} style={column}>
          {children}
        </div>
        <div ref={right} style={column} aria-label={t("compare.reference")} role="region">
          {reference}
        </div>
      </div>
    </>
  );
}

type Shown = { kind: "combined" } | { kind: "source"; key: string } | { kind: "version"; number: number };

/** The reference, read only: what the draft was written from, or another version. */
export function ReferencePanel({
  workspaceId,
  briefId,
  versions,
  current,
  documentSources,
  copied,
}: {
  workspaceId: string;
  briefId: string | null;
  versions: VersionView[];
  current: number;
  documentSources: { url?: string | null }[]; // the sources of the draft shown, in the order it cites them
  copied: string[]; // the start of the passages the guardrails found copied (U05)
}) {
  const { t } = useTranslation();
  const sources = useQuery({ ...briefSourcesQuery(workspaceId, briefId ?? ""), enabled: briefId !== null });
  const texts = sources.data ?? [];
  const fallback: Shown =
    texts.length > 1
      ? { kind: "combined" }
      : texts[0] !== undefined
        ? { kind: "source", key: texts[0].key }
        : { kind: "version", number: versions.find((v) => v.number !== current)?.number ?? current };
  const [chosen, setChosen] = useState<Shown | null>(null);
  const shown = chosen ?? fallback;
  const value = shown.kind === "combined" ? "combined" : shown.kind === "source" ? `s:${shown.key}` : `v:${String(shown.number)}`;
  // The number the draft gives a source in its references ([1], [2]…), by its address.
  const cited = (source: SourceTextView): number | null => {
    const index = documentSources.findIndex((s) => s.url != null && s.url === source.url);
    return index < 0 ? null : index + 1;
  };
  const version = shown.kind === "version" ? versions.find((v) => v.number === shown.number) : undefined;
  return (
    <section className={styles.panel}>
      <p className={styles.row}>
        <label htmlFor="compare-shown">{t("compare.show")}</label>
        <select
          id="compare-shown"
          style={{ maxWidth: "100%" }}
          value={value}
          onChange={(event) => {
            const picked = event.target.value;
            setChosen(
              picked === "combined"
                ? { kind: "combined" }
                : picked.startsWith("s:")
                  ? { kind: "source", key: picked.slice(2) }
                  : { kind: "version", number: Number(picked.slice(2)) },
            );
          }}
        >
          {texts.length > 1 && <option value="combined">{t("compare.combined", { count: texts.length })}</option>}
          {texts.map((source, index) => (
            <option key={source.key} value={`s:${source.key}`}>
              {t("compare.source", { number: index + 1, title: source.title.slice(0, 80) })}
            </option>
          ))}
          {versions.map((v) => (
            <option key={v.number} value={`v:${String(v.number)}`}>
              {t("compare.version", { number: v.number, words: v.words })}
              {v.number === current ? t("compare.current") : ""}
            </option>
          ))}
        </select>
      </p>
      {shown.kind !== "version" &&
        texts
          .filter((source) => shown.kind === "combined" || source.key === shown.key)
          .map((source) => <SourceText key={source.key} source={source} number={cited(source)} copied={copied} />)}
      {version !== undefined && (
        <DocumentView
          document={version.document as unknown as PlatformDocument}
          title={version.title}
          prefix={`ref-v${String(version.number)}`}
          mediaUrl={(id) => mediaUrl(workspaceId, id)}
        />
      )}
    </section>
  );
}

/** A source as the draft received it, its copied passages marked. */
function SourceText({ source, number, copied }: { source: SourceTextView; number: number | null; copied: string[] }) {
  const { t } = useTranslation();
  const paragraphs = source.text.split(/\n\s*\n|\n/).filter((p) => p.trim() !== "");
  return (
    <article className={styles.text}>
      <h3>
        {number === null ? "" : `[${String(number)}] `}
        {source.url ? (
          <a href={source.url} target="_blank" rel="noreferrer">
            {source.title}
          </a>
        ) : (
          source.title
        )}
      </h3>
      <p className={styles.meta}>
        {[source.publisher, source.published_at ? formatDate(source.published_at) : null, t("watch.words", { count: source.words })]
          .filter(Boolean)
          .join(" · ")}
        {number === null && ` · ${t("compare.notCited")}`}
      </p>
      {paragraphs.map((paragraph, index) => (
        <p key={index}>{marked(paragraph, copied)}</p>
      ))}
    </article>
  );
}

/** The paragraph, with the copied passages (their first words, as the guardrails name them) marked. */
function marked(paragraph: string, copied: string[]): ReactNode {
  const hit = copied
    .map((excerpt) => ({ excerpt, at: paragraph.indexOf(excerpt) }))
    .filter((found) => found.excerpt !== "" && found.at >= 0)
    .sort((a, b) => a.at - b.at)[0];
  if (hit === undefined) {
    return paragraph;
  }
  const end = hit.at + hit.excerpt.length;
  return (
    <>
      {paragraph.slice(0, hit.at)}
      <mark title="Passage repris dans le brouillon">{paragraph.slice(hit.at, end)}</mark>
      {marked(paragraph.slice(end), copied)}
    </>
  );
}
