// SPDX-License-Identifier: AGPL-3.0-or-later
// The passages the guardrails found copied from a source (U05), marked in the draft too when
// comparing (Joël, 2026-10-24): the same yellow as in the source, on both sides. A decoration
// only: nothing is written into the document.
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey, type EditorState } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

export const COPIED_CLASS = "otlet-copied";

/** Where the excerpts start and end in a text: [start, end] pairs, in order, not overlapping.
 * Matched by their words, as the guardrails read them: case and punctuation aside (« d'Europe »
 * in a source is « d Europe » in an excerpt). */
export function copiedRanges(text: string, excerpts: string[]): [number, number][] {
  const ranges: [number, number][] = [];
  for (const excerpt of excerpts) {
    const words = excerpt.match(/[\p{L}\p{N}]+/gu);
    if (words === null) {
      continue;
    }
    // Letters and digits only: nothing to escape.
    const pattern = new RegExp(words.join("[^\\p{L}\\p{N}]+"), "giu");
    for (const found of text.matchAll(pattern)) {
      ranges.push([found.index, found.index + found[0].length]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  return ranges.filter((range, index) => index === 0 || range[0] >= (ranges[index - 1]?.[1] ?? 0));
}

const key = new PluginKey<DecorationSet>("otlet-copied");

function decorations(state: EditorState, excerpts: string[]): DecorationSet {
  if (excerpts.length === 0) {
    return DecorationSet.empty;
  }
  const found: Decoration[] = [];
  state.doc.descendants((node, pos) => {
    if (!node.isTextblock) {
      return true;
    }
    // The text of the block, with the position of each character in the document.
    let text = "";
    const at: number[] = [];
    node.forEach((child, offset) => {
      if (child.isText && child.text !== undefined) {
        for (let i = 0; i < child.text.length; i++) {
          at.push(pos + 1 + offset + i);
        }
        text += child.text;
      }
    });
    for (const [start, end] of copiedRanges(text, excerpts)) {
      const from = at[start];
      const to = at[end - 1];
      if (from !== undefined && to !== undefined) {
        found.push(Decoration.inline(from, to + 1, { class: COPIED_CLASS }));
      }
    }
    return false;
  });
  return DecorationSet.create(state.doc, found);
}

/** Set the excerpts to mark (none when not comparing). */
export function setCopied(state: EditorState, excerpts: string[]) {
  return state.tr.setMeta(key, excerpts);
}

export const CopiedPassages = Extension.create({
  name: "copiedPassages",
  addProseMirrorPlugins() {
    let excerpts: string[] = [];
    return [
      new Plugin<DecorationSet>({
        key,
        state: {
          init: () => DecorationSet.empty,
          apply: (tr, set, _old, state) => {
            const asked = tr.getMeta(key) as string[] | undefined;
            if (asked !== undefined) {
              excerpts = asked;
              return decorations(state, excerpts);
            }
            return tr.docChanged ? decorations(state, excerpts) : set;
          },
        },
        props: {
          decorations: (state) => key.getState(state),
        },
      }),
    ];
  },
});
