// SPDX-License-Identifier: AGPL-3.0-or-later
// Concordance test (ADR-0023 §4), editor side: renders every document of tools/concordance with
// the editor's extensions, without a browser, and writes the HTML and the closed lists of the
// format into the folder given; tools/check_concordance.py compares them with the Python
// renderer, which is the reference. Run by CI: node tools/concordance.ts <folder>.
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { generateHTML } from "@tiptap/html";
import { COLORS, FONTS, HIGHLIGHTS, SIZES } from "../src/editor/format.ts";
import { extensions, type Source } from "../src/editor/schema.ts";

const corpus = new URL("../../tools/concordance/", import.meta.url);
const out = process.argv[2];
if (out === undefined) {
  throw new Error("usage: node tools/concordance.ts <folder>");
}
mkdirSync(out, { recursive: true });
const names = readdirSync(corpus).filter((name) => name.endsWith(".json"));
for (const name of names) {
  const doc = JSON.parse(readFileSync(new URL(name, corpus), "utf8")) as {
    attrs: { sources: Source[] };
  };
  const html = generateHTML(doc, extensions(doc.attrs.sources));
  writeFileSync(join(out, name.replace(/\.json$/, ".html")), html);
}
writeFileSync(
  join(out, "lists.json"),
  JSON.stringify({
    fonts: Object.fromEntries(Object.entries(FONTS).map(([key, font]) => [key, font.css])),
    sizes: SIZES,
    colors: COLORS.map(([value]) => value),
    highlights: HIGHLIGHTS.map(([value]) => value),
  }),
);
console.log(`rendered ${String(names.length)} documents with the editor's extensions`);
