// SPDX-License-Identifier: AGPL-3.0-or-later
// From the editor's JSON to the « Document plateforme v1 » the server checks: Tiptap gives every
// node and mark all their attributes, null when unset; the format keeps attributes on top-level
// blocks only, and no null in a mark. The server recomputes ids and origins (ADR-0036 §2).
import type { JSONContent } from "@tiptap/core";

type Attrs = Record<string, unknown>;

function marks(list: JSONContent["marks"]): JSONContent["marks"] {
  return list?.map((mark) => {
    const attrs = Object.fromEntries(Object.entries(mark.attrs ?? {}).filter(([, value]) => value !== null));
    return Object.keys(attrs).length > 0 ? { type: mark.type, attrs } : { type: mark.type };
  });
}

function nested(node: JSONContent): JSONContent {
  const out: JSONContent = {};
  if (node.type !== undefined) {
    out.type = node.type;
  }
  if (node.text !== undefined) {
    out.text = node.text;
  }
  const kept = marks(node.marks);
  if (kept !== undefined && kept.length > 0) {
    out.marks = kept;
  }
  if (node.content !== undefined) {
    out.content = node.content.map(nested);
  }
  return out;
}

/** The document to save, from what the editor holds. */
export function toDocument(json: JSONContent, attrs: Attrs): Attrs {
  return {
    type: "doc",
    attrs,
    content: (json.content ?? []).map((block) => {
      const out = nested(block);
      return { ...out, attrs: block.attrs ?? {} };
    }),
  };
}
