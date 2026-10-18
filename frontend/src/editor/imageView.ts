// SPDX-License-Identifier: AGPL-3.0-or-later
// An image in the editor (Joël, 2026-10-18): once clicked, a handle at each corner and quick
// sizes set its width, in % of the column, as the document keeps it; the alignment buttons of
// the ribbon place it. Plain DOM: no React inside the text.
import type { NodeViewRenderer } from "@tiptap/core";
import { WRAP_DEFAULT, WRAP_MAX } from "./schema.ts";

const PRESETS = [25, 50, 75, 100] as const;
const CORNERS = ["nw", "ne", "sw", "se"] as const;
const clamp = (width: number, most = 100) => Math.min(most, Math.max(10, Math.round(width)));

export function imageView(
  mediaUrl: (id: string) => string,
  labels: { size: (width: number) => string; handle: string; own: string; wrap: string },
): NodeViewRenderer {
  return ({ node, editor, getPos }) => {
    let current = node;
    const dom = document.createElement("figure");
    dom.className = "otlet-image";
    const img = document.createElement("img");
    const tools = document.createElement("span");
    tools.className = "otlet-image-tools";
    tools.contentEditable = "false";
    // The frame takes the width; the handles sit at its corners.
    const frame = document.createElement("span");
    frame.className = "otlet-image-frame";
    frame.append(img, tools);
    dom.append(frame);

    const set = (attrs: Record<string, unknown>) => {
      const pos = getPos();
      if (typeof pos !== "number") {
        return;
      }
      const { view } = editor;
      view.dispatch(view.state.tr.setNodeMarkup(pos, undefined, { ...current.attrs, ...attrs }));
    };
    const shown = () => (typeof current.attrs.width === "number" ? current.attrs.width : null);
    // The text flows around it: the figure floats at its side, at its width.
    const side = (): "left" | "right" | null => {
      const align: unknown = current.attrs.align;
      return current.attrs.wrap === true && (align === "left" || align === "right") ? align : null;
    };
    const most = () => (side() === null ? 100 : WRAP_MAX);
    const show = (width: number | null) => {
      const floating = side();
      if (floating !== null) {
        const share = width ?? WRAP_DEFAULT;
        dom.style.float = floating;
        dom.style.width = `${String(share)}%`;
        dom.style.margin = floating === "left" ? "0px 1em 1em 0px" : "0px 0px 1em 1em";
        frame.style.width = "100%";
        img.style.width = "100%";
        return;
      }
      dom.style.float = "";
      dom.style.width = "";
      dom.style.margin = "";
      frame.style.width = width === null ? "" : `${String(width)}%`;
      img.style.width = width === null ? "" : "100%";
    };

    const handles = CORNERS.map((corner) => {
      const handle = document.createElement("span");
      handle.className = `otlet-image-handle otlet-image-handle-${corner}`;
      handle.contentEditable = "false";
      if (corner === "se") {
        // One of them for the keyboard: the arrows change the width by 5 %.
        handle.tabIndex = 0;
        handle.setAttribute("role", "slider");
        handle.setAttribute("aria-label", labels.handle);
        handle.setAttribute("aria-valuemin", "10");
        handle.setAttribute("aria-valuemax", "100");
        handle.addEventListener("keydown", (event) => {
          const step =
            event.key === "ArrowRight" || event.key === "ArrowUp"
              ? 5
              : event.key === "ArrowLeft" || event.key === "ArrowDown"
                ? -5
                : 0;
          if (step !== 0) {
            event.preventDefault();
            set({ width: clamp((shown() ?? 100) + step, most()) });
          }
        });
      } else {
        handle.setAttribute("aria-hidden", "true");
      }
      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const start = event.clientX;
        const startWidth = img.getBoundingClientRect().width;
        const column = (dom.parentElement ?? dom).getBoundingClientRect().width || 1;
        // A corner on the left grows the image when pulled left; a centred image grows on both
        // sides, so the pointer moves half as far.
        const side = corner.endsWith("w") ? -1 : 1;
        const factor = current.attrs.align === "center" ? 2 : 1;
        let last = shown() ?? clamp((startWidth / column) * 100, most());
        handle.setPointerCapture(event.pointerId);
        const move = (moved: PointerEvent) => {
          last = clamp(((startWidth + side * factor * (moved.clientX - start)) / column) * 100, most());
          show(last);
        };
        const up = () => {
          handle.removeEventListener("pointermove", move);
          handle.removeEventListener("pointerup", up);
          set({ width: last });
        };
        handle.addEventListener("pointermove", move);
        handle.addEventListener("pointerup", up);
      });
      frame.append(handle);
      return handle;
    });

    const button = (text: string, width: number | null) => {
      const element = document.createElement("button");
      element.type = "button";
      element.dataset.width = String(width);
      element.textContent = text;
      element.addEventListener("mousedown", (event) => {
        event.preventDefault();
      });
      element.addEventListener("click", () => {
        set({ width: width === null ? null : clamp(width, most()) });
      });
      tools.append(element);
    };
    PRESETS.forEach((width) => {
      button(labels.size(width), width);
    });
    button(labels.own, null);
    const wrap = document.createElement("button");
    wrap.type = "button";
    wrap.textContent = labels.wrap;
    wrap.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    wrap.addEventListener("click", () => {
      const wrapping = side() === null;
      set(wrapping ? { wrap: true, width: clamp(shown() ?? WRAP_DEFAULT, WRAP_MAX) } : { wrap: false });
    });
    tools.append(wrap);

    const paint = () => {
      img.src = mediaUrl(String(current.attrs.media));
      img.alt = String(current.attrs.alt ?? "");
      const width = shown();
      show(width);
      const align: unknown = current.attrs.align;
      dom.style.textAlign = typeof align === "string" && side() === null ? align : "";
      // Only an image at the left or the right can have the text flow around it.
      wrap.hidden = align !== "left" && align !== "right";
      wrap.setAttribute("aria-pressed", String(side() !== null));
      handles[3]?.setAttribute("aria-valuenow", String(width ?? 100));
      for (const element of Array.from(tools.querySelectorAll<HTMLButtonElement>("button[data-width]"))) {
        element.setAttribute("aria-pressed", String(element.dataset.width === String(width)));
      }
    };
    paint();

    return {
      dom,
      update: (updated) => {
        if (updated.type !== current.type) {
          return false;
        }
        current = updated;
        paint();
        return true;
      },
      selectNode: () => {
        dom.classList.add("otlet-image-selected");
      },
      deselectNode: () => {
        dom.classList.remove("otlet-image-selected");
      },
      stopEvent: (event) =>
        event.target instanceof Node &&
        (tools.contains(event.target) || handles.some((handle) => handle.contains(event.target as Node))),
      ignoreMutation: () => true,
    };
  };
}
