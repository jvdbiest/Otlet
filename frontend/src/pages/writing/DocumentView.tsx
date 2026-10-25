// SPDX-License-Identifier: AGPL-3.0-or-later
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";
import { blockAnchor } from "./blocks.ts";
import { FONTS, type TextStyle } from "../../editor/format.ts";
import { WRAP_DEFAULT } from "../../editor/schema.ts";
import { copiedRanges } from "../../editor/copied.ts";
import { editorStyles } from "../../editor/styles.ts";

const DAY = new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium" });

// « Document plateforme v1 » (ADR-0023), as the API gives it: read-only here, edited with
// Tiptap in X03. The Python renderer remains the reference for what is published.
interface Mark {
  type: string;
  attrs?: { href?: string; source?: string; color?: string } & TextStyle;
}
interface Node {
  type: string;
  text?: string;
  marks?: Mark[];
  attrs?: { id?: string; origine?: string; level?: number; source?: string; alt?: string; align?: string; media?: string; width?: number; wrap?: boolean };
  content?: Node[];
}
interface Source {
  id: string;
  titre: string;
  editeur?: string;
  date?: string;
  url?: string;
}
export interface PlatformDocument {
  attrs: { sources: Source[]; langue: string };
  content: Node[];
}

function inline(
  nodes: Node[] | undefined,
  numbers: Map<string, number>,
  prefix: string,
  copied: string[] = [],
): ReactNode[] {
  return (nodes ?? []).map((node, index) => {
    let out: ReactNode = node.text === undefined ? "" : marked(node.text, copied);
    for (const mark of node.marks ?? []) {
      if (mark.type === "bold") {
        out = <strong>{out}</strong>;
      } else if (mark.type === "italic") {
        out = <em>{out}</em>;
      } else if (mark.type === "strike") {
        out = <s>{out}</s>;
      } else if (mark.type === "subscript") {
        out = <sub>{out}</sub>;
      } else if (mark.type === "superscript") {
        out = <sup>{out}</sup>;
      } else if (mark.type === "highlight" && mark.attrs?.color) {
        out = <mark style={{ backgroundColor: mark.attrs.color }}>{out}</mark>;
      } else if (mark.type === "text_style" && mark.attrs) {
        const { font, size, color } = mark.attrs;
        out = (
          <span
            style={{
              ...(font ? { fontFamily: FONTS[font].css } : {}),
              ...(size ? { fontSize: `${String(size)}pt` } : {}),
              ...(color ? { color } : {}),
            }}
          >
            {out}
          </span>
        );
      } else if (mark.type === "link" && mark.attrs?.href) {
        out = (
          <a href={mark.attrs.href} target="_blank" rel="noreferrer">
            {out}
          </a>
        );
      } else if (mark.type === "source_ref" && mark.attrs?.source) {
        const number = numbers.get(mark.attrs.source);
        out = (
          <a className="otlet-source-ref" data-source={mark.attrs.source} href={`#${prefix}-${mark.attrs.source}`}>
            <sup>{number === undefined ? out : `[${String(number)}]`}</sup>
          </a>
        );
      }
    }
    return <span key={index}>{out}</span>;
  });
}

function aligned(node: Node): CSSProperties | undefined {
  const align = node.attrs?.align;
  return align === "center" || align === "right" || align === "justify" || align === "left"
    ? { textAlign: align }
    : undefined;
}

type MediaUrl = (id: string) => string;

/** A text with the passages copied from a source marked, in the same yellow as the source. */
function marked(text: string, copied: string[]): ReactNode {
  const ranges = copiedRanges(text, copied);
  if (ranges.length === 0) {
    return text;
  }
  const parts: ReactNode[] = [];
  let at = 0;
  for (const [start, end] of ranges) {
    parts.push(text.slice(at, start), <mark key={start}>{text.slice(start, end)}</mark>);
    at = end;
  }
  parts.push(text.slice(at));
  return parts;
}

function figureStyle(node: Node): CSSProperties | undefined {
  const side = node.attrs?.align;
  if (node.attrs?.wrap && (side === "left" || side === "right")) {
    return {
      float: side,
      width: `${String(node.attrs.width ?? WRAP_DEFAULT)}%`,
      margin: side === "left" ? "0px 1em 1em 0px" : "0px 0px 1em 1em",
    };
  }
  return aligned(node);
}

function block(
  node: Node,
  numbers: Map<string, number>,
  prefix: string,
  key: number,
  mediaUrl: MediaUrl,
  copied: string[] = [],
): ReactNode {
  const content = node.content;
  const id = node.attrs?.id ? blockAnchor(prefix, node.attrs.id) : undefined;
  switch (node.type) {
    case "heading":
      return node.attrs?.level === 3 ? (
        <h4 key={key} id={id} style={aligned(node)}>
          {inline(content, numbers, prefix, copied)}
        </h4>
      ) : (
        <h3 key={key} id={id} style={aligned(node)}>
          {inline(content, numbers, prefix, copied)}
        </h3>
      );
    case "paragraph":
      return (
        <p key={key} id={id} style={aligned(node)}>
          {inline(content, numbers, prefix, copied)}
        </p>
      );
    case "bullet_list":
    case "ordered_list": {
      const items = (content ?? []).map((item, n) => (
        <li key={n}>{(item.content ?? []).map((child, m) => block(child, numbers, prefix, m, mediaUrl, copied))}</li>
      ));
      return node.type === "bullet_list" ? <ul key={key}>{items}</ul> : <ol key={key}>{items}</ol>;
    }
    case "citation":
    case "encadre":
      return (
        <blockquote key={key}>{(content ?? []).map((child, m) => block(child, numbers, prefix, m, mediaUrl, copied))}</blockquote>
      );
    case "separateur":
      return <hr key={key} />;
    case "image":
      return (
        <figure key={key} id={id} style={figureStyle(node)}>
          <img
            src={mediaUrl(node.attrs?.media ?? "")}
            alt={node.attrs?.alt ?? ""}
            style={
              node.attrs?.wrap ? { width: "100%" } : node.attrs?.width ? { width: `${String(node.attrs.width)}%` } : undefined
            }
          />
        </figure>
      );
    default:
      return null;
  }
}

/** A version of an article: its blocks, then its sources, numbered as the references cite them. */
export function DocumentView({
  document,
  title,
  prefix,
  mediaUrl,
  words,
  copied = [],
}: {
  document: PlatformDocument;
  title: string;
  prefix: string;
  mediaUrl: MediaUrl;
  words?: Map<string, number>; // of each source, by its id (Joël, 2026-10-19)
  copied?: string[]; // passages copied from a source, marked as in the source when comparing
}) {
  const { t } = useTranslation();
  const numbers = new Map(document.attrs.sources.map((source, index) => [source.id, index + 1]));
  return (
    <article className={`${styles.text} ${editorStyles.paper}`} lang={document.attrs.langue}>
      <h2>{title}</h2>
      {document.content.map((node, index) => block(node, numbers, prefix, index, mediaUrl, copied))}
      {document.attrs.sources.length > 0 && (
        <>
          <h3>{t("draft.sources")}</h3>
          <ol>
            {document.attrs.sources.map((source) => (
              <li key={source.id} id={`${prefix}-${source.id}`}>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.titre}
                  </a>
                ) : (
                  source.titre
                )}
                {source.editeur && <span className={styles.meta}> · {source.editeur}</span>}
                {source.date && <span className={styles.meta}> · {DAY.format(new Date(source.date))}</span>}
                {words?.has(source.id) === true && (
                  <span className={styles.meta}> · {t("watch.words", { count: words.get(source.id) ?? 0 })}</span>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </article>
  );
}
