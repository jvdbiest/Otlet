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

/** The id of a block of `type` whose text starts with `start` (a « … » ends it when it was
 * shortened): the warnings name blocks by their text, not by their id. A repeated paragraph
 * often starts as the one it repeats: `skip` passes over the first matches, as long as some
 * are left. */
export function findBlock(document: PlatformDocument, type: string, start: string, skip = 0): string | undefined {
  const flat = (value: string) => value.replace(/\s+/g, " ").trim();
  const wanted = flat(start.replace(/…$/, ""));
  const found: string[] = [];
  const walk = (nodes: Block[]) => {
    for (const node of nodes) {
      if (node.type === type && node.attrs?.id && flat(text(node)).startsWith(wanted)) {
        found.push(node.attrs.id);
      }
      walk(node.content ?? []);
    }
  };
  if (wanted) {
    walk(document.content);
  }
  return found.at(Math.min(skip, found.length - 1));
}
