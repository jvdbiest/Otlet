// SPDX-License-Identifier: AGPL-3.0-or-later
// S3.4 and S3.5: renders every corpus document (build/json/*.json, written by export.py)
// with Tiptap and with BlockNote, without a browser, into build/html-tiptap and
// build/html-blocknote. Also pastes the 10 pasted documents into Tiptap's own HTML parser
// and writes the resulting JSON into build/paste-tiptap, for the schema check.
import { readdirSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { generateHTML, generateJSON } from "@tiptap/html";
import { ServerBlockNoteEditor } from "@blocknote/server-util";
import { extensions } from "./tiptap-schema.mjs";

const build = new URL("../build/", import.meta.url).pathname;
const outputs = ["html-tiptap", "html-blocknote", "paste-tiptap"];
for (const folder of outputs) mkdirSync(join(build, folder), { recursive: true });

// --- BlockNote: our JSON -> BlockNote blocks (its own model) --------------------------------
const styles = (marks = []) =>
  Object.fromEntries(marks.filter((m) => m.type === "bold" || m.type === "italic").map((m) => [m.type, true]));

function inline(content = []) {
  return content.map((node) => {
    const link = (node.marks ?? []).find((m) => m.type === "link");
    const text = { type: "text", text: node.text, styles: styles(node.marks) };
    return link ? { type: "link", href: link.attrs.href, content: [text] } : text;
  });
}

function listItems(list) {
  const type = list.type === "ordered_list" ? "numberedListItem" : "bulletListItem";
  return list.content.map((item) => ({
    type,
    content: inline(item.content[0].content),
    children: item.content.slice(1).flatMap((child) => listItems(child)),
  }));
}

function toBlockNote(doc) {
  const sources = Object.fromEntries(doc.attrs.sources.map((s) => [s.id, s]));
  return doc.content.flatMap((block) => {
    switch (block.type) {
      case "heading":
        return [{ type: "heading", props: { level: block.attrs.level }, content: inline(block.content) }];
      case "paragraph":
        return [{ type: "paragraph", content: inline(block.content) }];
      case "bullet_list":
      case "ordered_list":
        return listItems(block);
      case "citation": {
        const source = sources[block.attrs.source];
        return [
          ...block.content.map((p) => ({ type: "quote", content: inline(p.content) })),
          { type: "paragraph", content: [{ type: "text", text: "— ", styles: {} }, { type: "link", href: source.url, content: [{ type: "text", text: source.titre, styles: {} }] }] },
        ];
      }
      case "encadre":
        return block.content.map((p) => ({ type: "paragraph", content: inline(p.content) }));
      case "image":
        return [{ type: "image", props: { url: block.attrs.media, caption: block.attrs.alt } }];
      case "separateur":
        return [{ type: "divider" }];
      default:
        throw new Error(`unknown block ${block.type}`);
    }
  });
}

const blocknote = ServerBlockNoteEditor.create();
const names = readdirSync(join(build, "json")).filter((n) => n.endsWith(".json"));
for (const name of names) {
  const doc = JSON.parse(readFileSync(join(build, "json", name), "utf8"));
  const tiptap = generateHTML(doc, extensions(doc.attrs.sources));
  writeFileSync(join(build, "html-tiptap", name.replace(/\.json$/, ".html")), tiptap);
  const bn = await blocknote.blocksToHTMLLossy(toBlockNote(doc));
  writeFileSync(join(build, "html-blocknote", name.replace(/\.json$/, ".html")), bn);
}

// Paste: the raw clipboard HTML through Tiptap's parser (what the editor does on paste).
const pasted = new URL("../corpus/pasted/", import.meta.url).pathname;
for (const name of readdirSync(pasted).filter((n) => n.endsWith(".html"))) {
  const sources = JSON.parse(readFileSync(join(pasted, name.replace(/\.html$/, ".sources.json")), "utf8"));
  const json = generateJSON(readFileSync(join(pasted, name), "utf8"), extensions(sources));
  // What the editor-to-format adapter does in the product: nested nodes carry no block
  // attributes (Tiptap gives every paragraph the same attributes), top-level blocks get
  // stable ids and a human origin.
  const strip = (node) => {
    if (node.attrs && Object.values(node.attrs).every((value) => value === null)) delete node.attrs;
    (node.content ?? []).forEach(strip);
  };
  json.content.forEach((block) => (block.content ?? []).forEach(strip));
  json.content.forEach((block, index) => {
    if (block.attrs) Object.assign(block.attrs, { id: `b${index + 1}`, origine: "humain" });
  });
  json.attrs = { version_schema: 1, langue: "fr", sources };
  writeFileSync(join(build, "paste-tiptap", name.replace(/\.html$/, ".json")), JSON.stringify(json, null, 2));
}
console.log(`rendered ${names.length} documents with Tiptap and BlockNote`);
