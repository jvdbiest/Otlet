// SPDX-License-Identifier: AGPL-3.0-or-later
// « Document plateforme v1 » (ADR-0023, ADR-0036) as Tiptap extensions. The node and mark names
// are those of the JSON; renderHTML reproduces the Python renderer (body only,
// otlet.writing.domain.document.render), which the concordance test checks
// (tools/concordance.ts, tools/check_concordance.py). Kept free of React and of the browser's
// globals at load time: Node runs it for the concordance test.
import { Mark, Node, type AnyExtension, type NodeViewRenderer } from "@tiptap/core";
import { ALIGNS, FONT_KEYS, FONTS, HIGHLIGHTS, SIZES, COLORS, hexColor, styleOf, type TextStyle } from "./format.ts";

export interface Source {
  id: string;
  titre: string;
  editeur?: string;
  date?: string;
  url?: string;
}

const hidden = (name: string, fallback: unknown = null) => ({ [name]: { default: fallback, rendered: false } });
// A block split in two keeps its id and origin in the first part only: the second is new, and the
// server gives it its id and origin (ADR-0036 §2).
const own = (name: string) => ({ [name]: { default: null, rendered: false, keepOnSplit: false } });
const blockAttrs = () => ({ ...own("id"), ...own("origine") });
// The alignment of a paragraph or a heading, kept when it is split (Joël, 2026-10-18).
const align = () => ({
  align: {
    default: null,
    rendered: false,
    parseHTML: (element: HTMLElement) =>
      (ALIGNS as readonly string[]).includes(element.style.textAlign) ? element.style.textAlign : null,
  },
});
const aligned = (align: unknown) => (typeof align === "string" && align ? { style: `text-align: ${align}` } : {});

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
  addAttributes: () => ({ ...blockAttrs(), ...align() }),
  parseHTML: () => [{ tag: "p" }],
  renderHTML: ({ node }) => ["p", aligned(node.attrs.align), 0],
});

const Heading = Node.create({
  name: "heading",
  group: "block",
  content: "inline*",
  defining: true,
  addAttributes: () => ({ ...blockAttrs(), ...hidden("level", 2), ...align() }),
  parseHTML: () =>
    [1, 2, 3, 4, 5, 6].map((level) => ({ tag: `h${String(level)}`, attrs: { level: Math.min(Math.max(level, 2), 4) } })),
  renderHTML: ({ node }) => [`h${String(node.attrs.level)}`, aligned(node.attrs.align), 0],
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

// An image of the workspace (X03b): the document keeps its id; its address comes from the page.
const ImageNode = Node.create<{ mediaUrl: (id: string) => string; mediaIdOf: (src: string) => string | null }>({
  name: "image",
  group: "block",
  atom: true,
  draggable: true,
  selectable: true,
  addOptions: () => ({ mediaUrl: (id: string) => id, mediaIdOf: () => null }),
  addAttributes: () => ({
    ...blockAttrs(),
    ...hidden("media"),
    ...hidden("alt", ""),
    ...align(),
    // In % of the column (Joël, 2026-10-18), from 10 to 100; none is the image's own width.
    width: {
      default: null,
      rendered: false,
      parseHTML: (element: HTMLElement) => {
        const width = /^(\d+)%$/.exec(element.style.width);
        return width ? Math.min(100, Math.max(10, Number(width[1]))) : null;
      },
    },
  }),
  parseHTML() {
    return [
      {
        tag: "img[src]",
        getAttrs: (element: HTMLElement) => {
          const media = this.options.mediaIdOf(element.getAttribute("src") ?? "");
          return media === null ? false : { media, alt: element.getAttribute("alt") ?? "" };
        },
      },
    ];
  },
  renderHTML({ node }) {
    const width = typeof node.attrs.width === "number" ? { style: `width: ${String(node.attrs.width)}%` } : {};
    return [
      "figure",
      aligned(node.attrs.align),
      ["img", { src: this.options.mediaUrl(String(node.attrs.media)), alt: String(node.attrs.alt ?? ""), ...width }],
    ];
  },
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

const Superscript = Mark.create({
  name: "superscript",
  excludes: "subscript",
  parseHTML: () => [{ tag: "sup" }, { style: "vertical-align=super" }],
  renderHTML: () => ["sup", 0],
  addKeyboardShortcuts() {
    return { "Mod-.": () => this.editor.commands.toggleMark(this.name) };
  },
});

const Subscript = Mark.create({
  name: "subscript",
  excludes: "superscript",
  parseHTML: () => [{ tag: "sub" }, { style: "vertical-align=sub" }],
  renderHTML: () => ["sub", 0],
  addKeyboardShortcuts() {
    return { "Mod-,": () => this.editor.commands.toggleMark(this.name) };
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

/** How the editor finds the images of the workspace: by default (the concordance test), an image
 * is shown at its id. */
export interface Media {
  mediaUrl: (id: string) => string;
  mediaIdOf: (src: string) => string | null;
  view?: NodeViewRenderer; // how the editor shows an image: with its handle (imageView.ts)
}

/** The extensions of the format; the editor adds its own (undo, paste cleaning). */
export function extensions(sources: Source[] = [], media?: Media): AnyExtension[] {
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
    media === undefined
      ? ImageNode
      : ImageNode.configure({ mediaUrl: media.mediaUrl, mediaIdOf: media.mediaIdOf }).extend({
          addNodeView: () => media.view ?? null,
        }),
    SourceRef,
    Link,
    TextStyleMark,
    Highlight,
    Superscript,
    Subscript,
    Strike,
    Italic,
    Bold,
  ];
}
