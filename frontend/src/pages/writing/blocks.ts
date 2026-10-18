// SPDX-License-Identifier: AGPL-3.0-or-later
import type { PlatformDocument } from "./DocumentView.tsx";

interface Block {
  type: string;
  text?: string;
  attrs?: { id?: string };
  content?: Block[];
}

/** The anchor of a block of a version, so a warning can lead to it. */
export function blockAnchor(prefix: string, id: string): string {
  return `${prefix}-b-${id}`;
}

function text(node: Block): string {
  return (node.content ?? []).map((child) => child.text ?? text(child)).join("");
}

/** The id of the first block of `type` whose text starts with `start` (a « … » ends it when
 * it was shortened): the warnings name blocks by their text, not by their id. */
export function findBlock(document: PlatformDocument, type: string, start: string): string | undefined {
  const flat = (value: string) => value.replace(/\s+/g, " ").trim();
  const wanted = flat(start.replace(/…$/, ""));
  const walk = (nodes: Block[]): string | undefined => {
    for (const node of nodes) {
      if (node.type === type && node.attrs?.id && flat(text(node)).startsWith(wanted)) {
        return node.attrs.id;
      }
      const inner = walk(node.content ?? []);
      if (inner !== undefined) {
        return inner;
      }
    }
    return undefined;
  };
  return wanted ? walk(document.content) : undefined;
}
