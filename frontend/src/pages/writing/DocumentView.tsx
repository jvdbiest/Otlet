// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";
import { blockAnchor } from "./blocks.ts";

const DAY = new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium" });

// « Document plateforme v1 » (ADR-0023), as the API gives it: read-only here, edited with
// Tiptap in X03. The Python renderer remains the reference for what is published.
interface Mark {
  type: string;
  attrs?: { href?: string; source?: string };
}
interface Node {
  type: string;
  text?: string;
  marks?: Mark[];
  attrs?: { id?: string; origine?: string; level?: number; source?: string; alt?: string };
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

function inline(nodes: Node[] | undefined, numbers: Map<string, number>, prefix: string): ReactNode[] {
  return (nodes ?? []).map((node, index) => {
    let out: ReactNode = node.text ?? "";
    for (const mark of node.marks ?? []) {
      if (mark.type === "bold") {
        out = <strong>{out}</strong>;
      } else if (mark.type === "italic") {
        out = <em>{out}</em>;
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

function block(node: Node, numbers: Map<string, number>, prefix: string, key: number): ReactNode {
  const content = node.content;
  const id = node.attrs?.id ? blockAnchor(prefix, node.attrs.id) : undefined;
  switch (node.type) {
    case "heading":
      return node.attrs?.level === 3 ? (
        <h4 key={key} id={id}>
          {inline(content, numbers, prefix)}
        </h4>
      ) : (
        <h3 key={key} id={id}>
          {inline(content, numbers, prefix)}
        </h3>
      );
    case "paragraph":
      return (
        <p key={key} id={id}>
          {inline(content, numbers, prefix)}
        </p>
      );
    case "bullet_list":
    case "ordered_list": {
      const items = (content ?? []).map((item, n) => (
        <li key={n}>{(item.content ?? []).map((child, m) => block(child, numbers, prefix, m))}</li>
      ));
      return node.type === "bullet_list" ? <ul key={key}>{items}</ul> : <ol key={key}>{items}</ol>;
    }
    case "citation":
    case "encadre":
      return (
        <blockquote key={key}>{(content ?? []).map((child, m) => block(child, numbers, prefix, m))}</blockquote>
      );
    case "separateur":
      return <hr key={key} />;
    default:
      return null;
  }
}

/** A version of an article: its blocks, then its sources, numbered as the references cite them. */
export function DocumentView({ document, title, prefix }: { document: PlatformDocument; title: string; prefix: string }) {
  const { t } = useTranslation();
  const numbers = new Map(document.attrs.sources.map((source, index) => [source.id, index + 1]));
  return (
    <article className={styles.text} lang={document.attrs.langue}>
      <h2>{title}</h2>
      {document.content.map((node, index) => block(node, numbers, prefix, index))}
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
              </li>
            ))}
          </ol>
        </>
      )}
    </article>
  );
}
