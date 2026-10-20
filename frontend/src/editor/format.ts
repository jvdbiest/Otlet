// SPDX-License-Identifier: AGPL-3.0-or-later
// The closed lists of the « Document plateforme v1 » (ADR-0036 §3), as in the Python module
// otlet.writing.domain.document: the concordance test checks both are the same.

/** Fonts: their key in the document, the CSS stack the HTML carries, the name shown. */
export const FONTS = {
  arial: { css: "Arial, Helvetica, sans-serif", label: "Arial" },
  calibri: { css: "Calibri, Carlito, sans-serif", label: "Calibri" },
  cambria: { css: "Cambria, Caladea, serif", label: "Cambria" },
  georgia: { css: "Georgia, serif", label: "Georgia" },
  times: { css: "'Times New Roman', Times, serif", label: "Times New Roman" },
  verdana: { css: "Verdana, Geneva, sans-serif", label: "Verdana" },
  courier: { css: "'Courier New', Courier, monospace", label: "Courier New" },
} as const;
export type FontKey = keyof typeof FONTS;
export const FONT_KEYS = Object.keys(FONTS) as FontKey[];

/** Sizes, in points. */
export const SIZES = [9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36] as const;

/** Text colours, and their name in French for the ribbon. */
export const COLORS = [
  ["#000000", "Noir"],
  ["#595959", "Gris"],
  ["#c00000", "Rouge"],
  ["#e36c09", "Orange"],
  ["#9c6500", "Brun"],
  ["#00843d", "Vert"],
  ["#0070c0", "Bleu"],
  ["#1f3864", "Bleu nuit"],
  ["#7030a0", "Violet"],
  ["#ffffff", "Blanc"],
] as const;

/** Highlight colours. */
export const HIGHLIGHTS = [
  ["#fff59d", "Jaune"],
  ["#c8e6c9", "Vert"],
  ["#b3e5fc", "Bleu"],
  ["#f8bbd0", "Rose"],
  ["#ffe0b2", "Orange"],
  ["#e0e0e0", "Gris"],
] as const;

/** Alignments of a paragraph or a heading; none is the site's own. */
export const ALIGNS = ["left", "center", "right", "justify"] as const;
export type Align = (typeof ALIGNS)[number];

export interface TextStyle {
  font?: FontKey | null;
  size?: number | null;
  color?: string | null;
}

/** The inline style of a « text_style » mark, its properties always in this order (as the
 * Python renderer writes it). */
export function styleOf(attrs: TextStyle): string {
  const parts: string[] = [];
  if (attrs.font) {
    parts.push(`font-family: ${FONTS[attrs.font].css}`);
  }
  if (attrs.size) {
    parts.push(`font-size: ${String(attrs.size)}pt`);
  }
  if (attrs.color) {
    parts.push(`color: ${attrs.color}`);
  }
  return parts.join("; ");
}

/** A CSS colour as the browser gives it back (« rgb(192, 0, 0) ») in the « #c00000 » form. */
export function hexColor(value: string): string {
  const rgb = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(value.trim());
  if (rgb === null) {
    return value.trim().toLowerCase();
  }
  return `#${rgb
    .slice(1, 4)
    .map((n) => Number(n).toString(16).padStart(2, "0"))
    .join("")}`;
}
