// SPDX-License-Identifier: AGPL-3.0-or-later
// S3.4: the "Document plateforme v1" schema as Tiptap extensions. The node and mark names are
// those of the JSON (schema/document-v1.schema.json); renderHTML mirrors the Python renderer
// (otlet_doc/render.py, body only), which is what the concordance test checks.
import { Mark, Node } from "@tiptap/core";

const hidden = (name, fallback = null) => ({ [name]: { default: fallback, rendered: false } });
const blockAttrs = () => ({ ...hidden("id"), ...hidden("origine") });

export const Doc = Node.create({
  name: "doc",
  topNode: true,
  content: "block+",
  addAttributes: () => ({ ...hidden("version_schema", 1), ...hidden("langue", "fr"), ...hidden("sources", []) }),
});

export const Text = Node.create({ name: "text", group: "inline" });

export const Paragraph = Node.create({
  name: "paragraph",
  group: "block",
  content: "inline*",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "p" }],
  renderHTML: () => ["p", 0],
});

export const Heading = Node.create({
  name: "heading",
  group: "block",
  content: "inline*",
  defining: true,
  addAttributes: () => ({ ...blockAttrs(), ...hidden("level", 2) }),
  parseHTML: () => [2, 3, 4].map((level) => ({ tag: `h${level}`, attrs: { level } })),
  renderHTML: ({ node }) => [`h${node.attrs.level}`, 0],
});

export const ListItem = Node.create({
  name: "list_item",
  content: "paragraph (paragraph | bullet_list | ordered_list)*",
  defining: true,
  parseHTML: () => [{ tag: "li" }],
  renderHTML: () => ["li", 0],
});

export const BulletList = Node.create({
  name: "bullet_list",
  group: "block",
  content: "list_item+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "ul" }],
  renderHTML: () => ["ul", 0],
});

export const OrderedList = Node.create({
  name: "ordered_list",
  group: "block",
  content: "list_item+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "ol" }],
  renderHTML: () => ["ol", 0],
});

// A typed quotation: its source is mandatory; the attribution comes from the document sources.
export const Citation = Node.create({
  name: "citation",
  group: "block",
  content: "paragraph+",
  defining: true,
  addOptions: () => ({ sources: [] }),
  addAttributes: () => ({ ...blockAttrs(), ...hidden("source") }),
  parseHTML: () => [{ tag: "div.otlet-citation", contentElement: "blockquote" }],
  renderHTML({ node }) {
    const source = this.options.sources.find((s) => s.id === node.attrs.source) ?? { url: "#", titre: "?" };
    return [
      "div",
      { class: "otlet-citation" },
      ["blockquote", 0],
      ["p", { class: "otlet-citation-source" }, "— ", ["a", { href: source.url }, source.titre]],
    ];
  },
});

export const Encadre = Node.create({
  name: "encadre",
  group: "block",
  content: "paragraph+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "aside.otlet-encadre" }],
  renderHTML: () => ["aside", { class: "otlet-encadre" }, 0],
});

export const Image = Node.create({
  name: "image",
  group: "block",
  atom: true,
  addAttributes: () => ({ ...blockAttrs(), ...hidden("media", ""), ...hidden("alt", "") }),
  renderHTML: ({ node }) => ["figure", ["img", { src: node.attrs.media, alt: node.attrs.alt }]],
});

export const Separateur = Node.create({
  name: "separateur",
  group: "block",
  atom: true,
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "hr" }],
  renderHTML: () => ["hr"],
});

// Mark order = nesting order, outermost first, as in the Python renderer.
export const SourceRef = Mark.create({
  name: "source_ref",
  addAttributes: () => ({ source: { default: null, rendered: false } }),
  parseHTML: () => [{ tag: "span.otlet-source-ref", getAttrs: (el) => ({ source: el.getAttribute("data-source") }) }],
  renderHTML: ({ mark }) => ["span", { class: "otlet-source-ref", "data-source": mark.attrs.source }, 0],
});

export const Link = Mark.create({
  name: "link",
  inclusive: false,
  addAttributes: () => ({ href: { default: null, rendered: false } }),
  parseHTML: () => [{ tag: "a[href]", getAttrs: (el) => ({ href: el.getAttribute("href") }) }],
  renderHTML: ({ mark }) => ["a", { href: mark.attrs.href }, 0],
});

export const Italic = Mark.create({
  name: "italic",
  parseHTML: () => [{ tag: "em" }, { tag: "i" }, { style: "font-style=italic" }],
  renderHTML: () => ["em", 0],
});

export const Bold = Mark.create({
  name: "bold",
  parseHTML: () => [{ tag: "strong" }, { tag: "b", getAttrs: (el) => el.style.fontWeight !== "normal" && null }],
  renderHTML: () => ["strong", 0],
});

export function extensions(sources = []) {
  return [
    Doc, Text, Paragraph, Heading, ListItem, BulletList, OrderedList,
    Citation.configure({ sources }), Encadre, Image, Separateur,
    SourceRef, Link, Italic, Bold,
  ];
}
