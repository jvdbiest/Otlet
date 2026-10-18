// SPDX-License-Identifier: AGPL-3.0-or-later
// « Document plateforme v1 » (ADR-0023, ADR-0036) as Tiptap extensions. The node and mark names
// are those of the JSON; renderHTML reproduces the Python renderer (body only,
// otlet.writing.domain.document.render), which the concordance test checks
// (tools/concordance.ts, tools/check_concordance.py). Kept free of React and of the browser's
// globals at load time: Node runs it for the concordance test.
import { Mark, Node, type AnyExtension } from "@tiptap/core";
import { FONT_KEYS, FONTS, HIGHLIGHTS, SIZES, COLORS, hexColor, styleOf, type TextStyle } from "./format.ts";

export interface Source {
  id: string;
  titre: string;
  editeur?: string;
  date?: string;
  url?: string;
}

const hidden = (name: string, fallback: unknown = null) => ({ [name]: { default: fallback, rendered: false } });
const blockAttrs = () => ({ ...hidden("id"), ...hidden("origine") });

const Doc = Node.create({
  name: "doc",
  topNode: true,
  content: "block+",
  addAttributes: () => ({ ...hidden("version_schema", 1), ...hidden("langue", "fr"), ...hidden("sources", []) }),
});

const Text = Node.create({ name: "text", group: "inline" });

const Paragraph = Node.create({
  name: "paragraph",
  group: "block",
  content: "inline*",
  priority: 1000,
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "p" }],
  renderHTML: () => ["p", 0],
});

const Heading = Node.create({
  name: "heading",
  group: "block",
  content: "inline*",
  defining: true,
  addAttributes: () => ({ ...blockAttrs(), ...hidden("level", 2) }),
  parseHTML: () =>
    [1, 2, 3, 4, 5, 6].map((level) => ({ tag: `h${String(level)}`, attrs: { level: Math.min(Math.max(level, 2), 4) } })),
  renderHTML: ({ node }) => [`h${String(node.attrs.level)}`, 0],
});

const ListItem = Node.create({
  name: "list_item",
  content: "paragraph (paragraph | bullet_list | ordered_list)*",
  defining: true,
  parseHTML: () => [{ tag: "li" }],
  renderHTML: () => ["li", 0],
  addKeyboardShortcuts() {
    return {
      Enter: () => this.editor.commands.splitListItem(this.name),
      Tab: () => this.editor.commands.sinkListItem(this.name),
      "Shift-Tab": () => this.editor.commands.liftListItem(this.name),
    };
  },
});

const BulletList = Node.create({
  name: "bullet_list",
  group: "block",
  content: "list_item+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "ul" }],
  renderHTML: () => ["ul", 0],
});

const OrderedList = Node.create({
  name: "ordered_list",
  group: "block",
  content: "list_item+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "ol" }],
  renderHTML: () => ["ol", 0],
});

// A typed quotation: its source is mandatory; the attribution comes from the document sources.
const Citation = Node.create<{ sources: Source[] }>({
  name: "citation",
  group: "block",
  content: "paragraph+",
  defining: true,
  addOptions: () => ({ sources: [] }),
  addAttributes: () => ({
    ...blockAttrs(),
    source: {
      default: null,
      rendered: false,
      parseHTML: (element: HTMLElement) => element.getAttribute("data-source"),
    },
  }),
  parseHTML: () => [{ tag: "div.otlet-citation", contentElement: "blockquote" }],
  renderHTML({ node }) {
    const source = this.options.sources.find((s) => s.id === node.attrs.source);
    const title = source?.titre ?? "?";
    return [
      "div",
      { class: "otlet-citation" },
      ["blockquote", 0],
      ["p", { class: "otlet-citation-source" }, "— ", source?.url ? ["a", { href: source.url }, title] : title],
    ];
  },
});

const Encadre = Node.create({
  name: "encadre",
  group: "block",
  content: "paragraph+",
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "aside.otlet-encadre" }],
  renderHTML: () => ["aside", { class: "otlet-encadre" }, 0],
});

const Separateur = Node.create({
  name: "separateur",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes: blockAttrs,
  parseHTML: () => [{ tag: "hr" }],
  renderHTML: () => ["hr"],
});

// The marks, outermost first: ProseMirror nests them in this order, the Python renderer too.
const SourceRef = Mark.create({
  name: "source_ref",
  inclusive: false,
  addAttributes: () => ({ source: { default: null, rendered: false } }),
  parseHTML: () => [
    { tag: "span.otlet-source-ref", getAttrs: (element: HTMLElement) => ({ source: element.getAttribute("data-source") }) },
  ],
  renderHTML: ({ mark }) => ["span", { class: "otlet-source-ref", "data-source": mark.attrs.source as string }, 0],
});

const SAFE_LINK = /^(https?:\/\/|mailto:)[^\s<>"]+$/i;

const Link = Mark.create({
  name: "link",
  inclusive: false,
  addAttributes: () => ({ href: { default: null, rendered: false } }),
  parseHTML: () => [
    {
      tag: "a[href]",
      getAttrs: (element: HTMLElement) => {
        const href = element.getAttribute("href") ?? "";
        return SAFE_LINK.test(href) ? { href } : false;
      },
    },
  ],
  renderHTML: ({ mark }) => ["a", { href: mark.attrs.href as string }, 0],
});

const flat = (value: string) => value.replace(/["']/g, "").replace(/\s+/g, "").toLowerCase();

/** The « text_style » of an element's inline style, if its values are in the lists. */
function parseStyle(element: HTMLElement): TextStyle | false {
  if (element.classList.contains("otlet-source-ref")) {
    return false;
  }
  const attrs: TextStyle = {};
  const font = FONT_KEYS.find((key) => flat(FONTS[key].css) === flat(element.style.fontFamily));
  if (font) {
    attrs.font = font;
  }
  const size = /^(\d+)pt$/.exec(element.style.fontSize);
  if (size && (SIZES as readonly number[]).includes(Number(size[1]))) {
    attrs.size = Number(size[1]);
  }
  const color = hexColor(element.style.color);
  if (COLORS.some(([value]) => value === color)) {
    attrs.color = color;
  }
  return Object.keys(attrs).length > 0 ? attrs : false;
}

const TextStyleMark = Mark.create({
  name: "text_style",
  addAttributes: () => ({ ...hidden("font"), ...hidden("size"), ...hidden("color") }),
  parseHTML: () => [{ tag: "span[style]", getAttrs: parseStyle }],
  renderHTML: ({ mark }) => ["span", { style: styleOf(mark.attrs as TextStyle) }, 0],
});

const Highlight = Mark.create({
  name: "highlight",
  addAttributes: () => ({ ...hidden("color") }),
  parseHTML: () => [
    {
      tag: "mark",
      getAttrs: (element: HTMLElement) => {
        const color = hexColor(element.style.backgroundColor);
        return { color: HIGHLIGHTS.some(([value]) => value === color) ? color : HIGHLIGHTS[0][0] };
      },
    },
  ],
  renderHTML: ({ mark }) => ["mark", { style: `background-color: ${String(mark.attrs.color)}` }, 0],
  addKeyboardShortcuts() {
    return { "Mod-Shift-h": () => this.editor.commands.toggleMark(this.name, { color: HIGHLIGHTS[0][0] }) };
  },
});

const Strike = Mark.create({
  name: "strike",
  parseHTML: () => [{ tag: "s" }, { tag: "del" }, { tag: "strike" }, { style: "text-decoration=line-through" }],
  renderHTML: () => ["s", 0],
  addKeyboardShortcuts() {
    return { "Mod-Shift-x": () => this.editor.commands.toggleMark(this.name) };
  },
});

const Italic = Mark.create({
  name: "italic",
  parseHTML: () => [{ tag: "em" }, { tag: "i" }, { style: "font-style=italic" }],
  renderHTML: () => ["em", 0],
  addKeyboardShortcuts() {
    return { "Mod-i": () => this.editor.commands.toggleMark(this.name) };
  },
});

const Bold = Mark.create({
  name: "bold",
  parseHTML: () => [
    { tag: "strong" },
    { tag: "b", getAttrs: (element: HTMLElement) => element.style.fontWeight !== "normal" && null },
  ],
  renderHTML: () => ["strong", 0],
  addKeyboardShortcuts() {
    return { "Mod-b": () => this.editor.commands.toggleMark(this.name) };
  },
});

/** The extensions of the format; the editor adds its own (undo, paste cleaning). */
export function extensions(sources: Source[] = []): AnyExtension[] {
  return [
    Doc,
    Text,
    Paragraph,
    Heading,
    ListItem,
    BulletList,
    OrderedList,
    Citation.configure({ sources }),
    Encadre,
    Separateur,
    SourceRef,
    Link,
    TextStyleMark,
    Highlight,
    Strike,
    Italic,
    Bold,
  ];
}
