// SPDX-License-Identifier: AGPL-3.0-or-later
// The paste cleaner (ADR-0023 §5): HTML pasted from Word or Google Docs becomes the HTML of the
// format before the editor parses it. It keeps headings, paragraphs, lists (nested), bold,
// italic, strike, links and quotations; everything else (styles, classes, Word's conditional
// comments and list bullets) is dropped. The rules are those of the S3 cleaner
// (spikes/s3-document/otlet_doc/paste.py). A quotation is a paragraph styled as a quote (Word:
// MsoQuote; Google Docs: a left margin of 30 pt or more) followed by an attribution starting
// with « — » whose link is one of the article's sources; otherwise its text stays as paragraphs.
import type { Source } from "./schema.ts";

type Mark = "strong" | "em" | "s" | { href: string };

interface Run {
  text: string;
  marks: Mark[];
}

interface Block {
  kind: "heading" | "paragraph" | "quote" | "item";
  level: number;
  ordered: boolean | null;
  runs: Run[];
}

const MARGIN = /margin-left:\s*([\d.]+)\s*pt/i;
const MSO_LIST = /mso-list:\s*\w+\s+level(\d+)/i;
const SAFE_LINK = /^(https?:\/\/|mailto:)[^\s<>"]+$/i;

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function plain(block: Block): string {
  return block.runs.map((run) => run.text).join("").trim();
}

function collect(body: HTMLElement): Block[] {
  const blocks: Block[] = [];
  let current: Block | null = null;
  const lists: string[] = []; // Google Docs: the open <ul> and <ol>
  let skipping = false; // between Word's « [if !supportLists] » and « [endif] »

  const open = (kind: Block["kind"], level = 1, ordered: boolean | null = null) => {
    current = { kind, level, ordered, runs: [] };
    blocks.push(current);
  };

  const walk = (node: ChildNode, marks: Mark[]) => {
    if (node.nodeType === Node.COMMENT_NODE) {
      const data = (node as Comment).data.trim();
      if (data.startsWith("[if !supportLists]")) {
        skipping = true;
      } else if (data.startsWith("[endif]")) {
        skipping = false;
      }
      return;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      const text = (node.textContent ?? "").replace(/\u00a0/g, " ").replace(/\s+/g, " ");
      const block = current;
      if (skipping) {
        // Word's list bullet: a number says the list is ordered.
        const marker = text.trim();
        if (block?.kind === "item" && marker && block.ordered === null) {
          block.ordered = /^\d+[.)]?$/.test(marker);
        }
        return;
      }
      if (!text.trim() && (block === null || block.runs.length === 0)) {
        return;
      }
      if (block === null) {
        open("paragraph");
      }
      current?.runs.push({ text, marks });
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return;
    }
    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    if (["style", "script", "title", "head", "meta", "img", "svg"].includes(tag)) {
      return;
    }
    const style = (element.getAttribute("style") ?? "").replace(/\s/g, "").toLowerCase();
    if (style.includes("mso-list:ignore")) {
      skipping = true;
      Array.from(element.childNodes).forEach((child) => {
        walk(child, marks);
      });
      skipping = false;
      return;
    }
    if (tag === "ul" || tag === "ol") {
      lists.push(tag);
      Array.from(element.childNodes).forEach((child) => {
        walk(child, marks);
      });
      lists.pop();
      return;
    }
    let inItem = false;
    if (/^h[1-6]$/.test(tag)) {
      open("heading", Math.min(Math.max(Number(tag[1]), 2), 4));
    } else if (tag === "li") {
      const level = Number(element.getAttribute("aria-level")) || lists.length || 1;
      open("item", level, lists.at(-1) === "ol");
      inItem = true;
    } else if (tag === "p" || tag === "div") {
      const klass = element.getAttribute("class") ?? "";
      const raw = element.getAttribute("style") ?? "";
      const mso = MSO_LIST.exec(raw);
      const margin = MARGIN.exec(raw);
      const block = current;
      if (mso && klass.includes("MsoListParagraph")) {
        open("item", Number(mso[1]), null);
      } else if (klass.includes("MsoQuote") || klass.includes("IntenseQuote") || (margin && Number(margin[1]) >= 30)) {
        open("quote");
      } else if (block?.kind === "item" && element.closest("li") !== null && block.runs.length === 0) {
        // Google Docs: <li><p>…</p></li>, one item.
      } else if (tag === "p" || element.querySelector("p, div, h1, h2, h3, h4, h5, h6, li") === null) {
        open("paragraph");
      }
    }
    let mark: Mark | null = null;
    if ((tag === "b" || tag === "strong") && !style.includes("font-weight:normal")) {
      mark = "strong";
    } else if (tag === "i" || tag === "em" || style.includes("font-style:italic")) {
      mark = "em";
    } else if (tag === "s" || tag === "del" || tag === "strike" || style.includes("line-through")) {
      mark = "s";
    } else if (tag === "span" && (style.includes("font-weight:700") || style.includes("font-weight:bold"))) {
      mark = "strong";
    } else if (tag === "a" && SAFE_LINK.test(element.getAttribute("href") ?? "")) {
      mark = { href: element.getAttribute("href") ?? "" };
    }
    const inner = mark === null ? marks : [...marks, mark];
    Array.from(element.childNodes).forEach((child) => {
      walk(child, inner);
    });
    if (inItem || tag === "p" || /^h[1-6]$/.test(tag)) {
      current = null;
    }
  };

  Array.from(body.childNodes).forEach((child) => {
    walk(child, []);
  });
  return blocks.filter((block) => plain(block) !== "");
}

function sameMarks(a: Mark[], b: Mark[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function inline(runs: Run[]): string {
  const merged: Run[] = [];
  for (const run of runs) {
    const last = merged.at(-1);
    if (last && sameMarks(last.marks, run.marks)) {
      last.text += run.text;
    } else {
      merged.push({ text: run.text, marks: run.marks });
    }
  }
  const first = merged[0];
  const last = merged.at(-1);
  if (first) {
    first.text = first.text.trimStart();
  }
  if (last) {
    last.text = last.text.trimEnd();
  }
  return merged
    .filter((run) => run.text)
    .map((run) => {
      let html = escapeHtml(run.text);
      for (const mark of [...run.marks].reverse()) {
        html = typeof mark === "string" ? `<${mark}>${html}</${mark}>` : `<a href="${escapeHtml(mark.href)}">${html}</a>`;
      }
      return html;
    })
    .join("");
}

function list(items: Block[]): string {
  const build = (start: number, level: number): [string, number] => {
    const tag = items[start]?.ordered ? "ol" : "ul";
    const parts: string[] = [];
    let index = start;
    for (let item = items[index]; item !== undefined && item.level >= level; item = items[index]) {
      if (item.level > level) {
        const [child, next] = build(index, item.level);
        const lastItem = parts.pop() ?? "<li><p></p>";
        parts.push(lastItem + child);
        index = next;
        continue;
      }
      parts.push(`<li><p>${inline(item.runs)}</p>`);
      index += 1;
    }
    return [`<${tag}>${parts.map((part) => `${part}</li>`).join("")}</${tag}>`, index];
  };
  return build(0, items[0]?.level ?? 1)[0];
}

/** The HTML of the format for HTML pasted from elsewhere. HTML copied inside Otlet's editor
 * (marked by ProseMirror) is kept as it is: it is already the format. */
export function cleanPastedHtml(html: string, sources: Source[]): string {
  if (html.includes("data-pm-slice")) {
    return html;
  }
  const body = new DOMParser().parseFromString(html, "text/html").body;
  const raw = collect(body);
  const byUrl = new Map(sources.filter((s) => s.url).map((s) => [s.url, s.id]));
  const out: string[] = [];
  let index = 0;
  for (let block = raw[0]; block !== undefined; block = raw[index]) {
    if (block.kind === "heading") {
      out.push(`<h${String(block.level)}>${inline(block.runs)}</h${String(block.level)}>`);
      index += 1;
    } else if (block.kind === "quote") {
      const quoted = [block];
      index += 1;
      for (let next = raw[index]; next?.kind === "quote" && !plain(next).startsWith("—"); next = raw[index]) {
        quoted.push(next);
        index += 1;
      }
      const attribution = raw[index];
      const source =
        attribution && plain(attribution).startsWith("—")
          ? attribution.runs
              .flatMap((run) => run.marks)
              .map((mark) => (typeof mark === "string" ? undefined : byUrl.get(mark.href)))
              .find((id) => id !== undefined)
          : undefined;
      if (source === undefined) {
        out.push(...quoted.map((q) => `<p>${inline(q.runs)}</p>`));
        continue;
      }
      index += 1;
      out.push(
        `<div class="otlet-citation" data-source="${escapeHtml(source)}"><blockquote>${quoted
          .map((q) => `<p>${inline(q.runs)}</p>`)
          .join("")}</blockquote></div>`,
      );
    } else if (block.kind === "item") {
      const items: Block[] = [];
      for (let next = raw[index]; next?.kind === "item"; next = raw[index]) {
        items.push(next);
        index += 1;
      }
      out.push(list(items));
    } else {
      out.push(`<p>${inline(block.runs)}</p>`);
      index += 1;
    }
  }
  return out.join("");
}
