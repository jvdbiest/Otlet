// SPDX-License-Identifier: AGPL-3.0-or-later
// An image in the editor (Joël, 2026-10-18): once clicked, a handle to drag and quick sizes set
// its width, in % of the column, as the document keeps it. Plain DOM: no React inside the text.
import type { NodeViewRenderer } from "@tiptap/core";

const PRESETS = [25, 50, 75, 100] as const;
const clamp = (width: number) => Math.min(100, Math.max(10, Math.round(width)));

export function imageView(
  mediaUrl: (id: string) => string,
  labels: { size: (width: number) => string; handle: string; own: string },
): NodeViewRenderer {
  return ({ node, editor, getPos }) => {
    let current = node;
    const dom = document.createElement("figure");
    dom.className = "otlet-image";
    const img = document.createElement("img");
    const tools = document.createElement("span");
    tools.className = "otlet-image-tools";
    tools.contentEditable = "false";
    const handle = document.createElement("span");
    handle.className = "otlet-image-handle";
    handle.contentEditable = "false";
    handle.tabIndex = 0;
    handle.setAttribute("role", "slider");
    handle.setAttribute("aria-label", labels.handle);
    handle.setAttribute("aria-valuemin", "10");
    handle.setAttribute("aria-valuemax", "100");
    // The frame takes the width; the handle sits at its corner.
    const frame = document.createElement("span");
    frame.className = "otlet-image-frame";
    frame.append(img, handle);
    dom.append(frame, tools);

    const set = (width: number | null) => {
      const pos = getPos();
      if (typeof pos !== "number") {
        return;
      }
      const { view } = editor;
      view.dispatch(view.state.tr.setNodeMarkup(pos, undefined, { ...current.attrs, width }));
    };
    const shown = () => (typeof current.attrs.width === "number" ? current.attrs.width : null);
    const paint = () => {
      img.src = mediaUrl(String(current.attrs.media));
      img.alt = String(current.attrs.alt ?? "");
      const width = shown();
      frame.style.width = width === null ? "" : `${String(width)}%`;
      img.style.width = width === null ? "" : "100%";
      handle.setAttribute("aria-valuenow", String(width ?? 100));
      for (const button of Array.from(tools.querySelectorAll("button"))) {
        button.setAttribute("aria-pressed", String(Number(button.dataset.width) === width));
      }
    };
    for (const width of PRESETS) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.width = String(width);
      button.textContent = labels.size(width);
      button.addEventListener("mousedown", (event) => {
        event.preventDefault();
      });
      button.addEventListener("click", () => {
        set(width);
      });
      tools.append(button);
    }
    const own = document.createElement("button");
    own.type = "button";
    own.textContent = labels.own;
    own.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    own.addEventListener("click", () => {
      set(null);
    });
    tools.append(own);

    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const start = event.clientX;
      const startWidth = img.getBoundingClientRect().width;
      const column = dom.getBoundingClientRect().width || 1;
      let last = shown() ?? clamp((startWidth / column) * 100);
      handle.setPointerCapture(event.pointerId);
      const move = (moved: PointerEvent) => {
        last = clamp(((startWidth + moved.clientX - start) / column) * 100);
        frame.style.width = `${String(last)}%`;
        img.style.width = "100%";
      };
      const up = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        set(last);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
    });
    handle.addEventListener("keydown", (event) => {
      const step = event.key === "ArrowRight" || event.key === "ArrowUp" ? 5 : event.key === "ArrowLeft" || event.key === "ArrowDown" ? -5 : 0;
      if (step !== 0) {
        event.preventDefault();
        set(clamp((shown() ?? 100) + step));
      }
    });
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
      stopEvent: (event) => event.target instanceof Node && (tools.contains(event.target) || handle.contains(event.target)),
      ignoreMutation: () => true,
    };
  };
}
