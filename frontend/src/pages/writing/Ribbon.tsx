// SPDX-License-Identifier: AGPL-3.0-or-later
import type { Editor } from "@tiptap/core";
import { useEditorState } from "@tiptap/react";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ALIGNS, COLORS, FONT_KEYS, FONTS, HIGHLIGHTS, SIZES, type Align, type TextStyle } from "../../editor/format.ts";
import { editorStyles } from "../../editor/styles.ts";
import { IMAGE_TYPES } from "../../media.ts";

const SAFE_LINK = /^(https?:\/\/|mailto:)[^\s<>"]+$/i;
const PRESENTATION = ["bold", "italic", "strike", "subscript", "superscript", "highlight", "text_style"] as const;

type Tool =
  | "undo"
  | "redo"
  | "cut"
  | "copy"
  | "paste"
  | "bold"
  | "italic"
  | "strike"
  | "subscript"
  | "superscript"
  | "bullet"
  | "ordered"
  | "link"
  | "separator"
  | "clear"
  | Align;

/** Sets one property of the « text_style » mark, keeping the others; the mark goes when it has
 * none left. */
function setStyle(editor: Editor, key: keyof TextStyle, value: string | number | null) {
  const attrs = { ...(editor.getAttributes("text_style") as TextStyle), [key]: value };
  const chain = editor.chain().focus();
  if (!attrs.font && !attrs.size && !attrs.color) {
    chain.unsetMark("text_style").run();
  } else {
    chain.setMark("text_style", attrs).run();
  }
}

/** The selection as the clipboard gets it from the editor itself: HTML that pastes back with
 * its formatting, and plain text. */
async function copySelection(editor: Editor): Promise<void> {
  const { dom, text } = editor.view.serializeForClipboard(editor.state.selection.content());
  await navigator.clipboard.write([
    new ClipboardItem({
      "text/html": new Blob([dom.innerHTML], { type: "text/html" }),
      "text/plain": new Blob([text], { type: "text/plain" }),
    }),
  ]);
}

/** The font and size the text at the cursor is shown in: its own, or those of its paragraph or
 * heading, read from the page (Joël, 2026-10-18: the menus show what is applied). */
function shown(editor: Editor): { font: string; size: number | null } {
  const style = editor.getAttributes("text_style") as TextStyle;
  let font: string = style.font ?? "";
  let size = style.size ?? null;
  if (font && size) {
    return { font, size };
  }
  const at = editor.view.domAtPos(editor.state.selection.from).node;
  const element = at instanceof Element ? at : at.parentElement;
  if (element === null) {
    return { font, size };
  }
  const computed = getComputedStyle(element);
  if (!font) {
    const first = computed.fontFamily.split(",")[0]?.replace(/["']/g, "").trim().toLowerCase() ?? "";
    font = FONT_KEYS.find((key) => FONTS[key].label.toLowerCase() === first) ?? "";
  }
  size ??= Math.round(parseFloat(computed.fontSize) * 0.75);
  return { font, size };
}

const ICONS: Record<Align, ReactNode> = {
  left: (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path d="M1 3h14M1 6.5h9M1 10h14M1 13.5h9" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  center: (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path d="M1 3h14M3.5 6.5h9M1 10h14M3.5 13.5h9" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  right: (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path d="M1 3h14M6 6.5h9M1 10h14M6 13.5h9" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  justify: (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path d="M1 3h14M1 6.5h14M1 10h14M1 13.5h14" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
};

/** A « A » button that opens a palette: the colour of the text, or its highlight. */
function Palette({
  label,
  value,
  colors,
  none,
  highlight,
  disabled,
  onPick,
}: {
  label: string;
  value: string;
  colors: readonly (readonly [string, string])[];
  none: string;
  highlight: boolean;
  disabled: boolean;
  onPick: (color: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const pick = (color: string | null) => {
    setOpen(false);
    onPick(color);
  };
  return (
    <span
      className={editorStyles.picker}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className={editorStyles.tool}
        title={label}
        aria-label={label}
        aria-haspopup="true"
        aria-expanded={open}
        disabled={disabled}
        onMouseDown={(event) => {
          event.preventDefault();
        }}
        onClick={() => {
          setOpen(!open);
        }}
      >
        {highlight ? (
          <span className={editorStyles.letter} style={{ backgroundColor: value || "transparent", color: "#000000" }}>
            A
          </span>
        ) : (
          <span className={editorStyles.letter} style={{ borderBottom: `4px solid ${value || "#000000"}` }}>
            A
          </span>
        )}
        <span aria-hidden="true"> ▾</span>
      </button>
      {open && (
        <span className={editorStyles.swatches} role="group" aria-label={label}>
          <button
            type="button"
            className={editorStyles.noColor}
            onMouseDown={(event) => {
              event.preventDefault();
            }}
            onClick={() => {
              pick(null);
            }}
          >
            {none}
          </button>
          {colors.map(([color, name]) => (
            <button
              key={color}
              type="button"
              className={editorStyles.swatch}
              style={{ backgroundColor: color }}
              title={name}
              aria-label={name}
              aria-pressed={value === color}
              onMouseDown={(event) => {
                event.preventDefault();
              }}
              onClick={() => {
                pick(color);
              }}
            />
          ))}
        </span>
      )}
    </span>
  );
}

/** The ribbon of the editor (X03, ADR-0036). `disabled` while the cursor is in the title, which
 * stays plain text. */
export function Ribbon({
  editor,
  disabled,
  onClipboardRefused,
  onImages,
}: {
  editor: Editor;
  disabled: boolean;
  onClipboardRefused: () => void;
  onImages: (files: File[]) => void;
}) {
  const { t } = useTranslation();
  const picker = useRef<HTMLInputElement>(null);
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      const style = e.getAttributes("text_style") as TextStyle;
      const level = e.getAttributes("heading").level as number | undefined;
      const block = e.isActive("heading") ? "heading" : "paragraph";
      const view = shown(e);
      return {
        canUndo: e.can().undo(),
        canRedo: e.can().redo(),
        empty: e.state.selection.empty,
        bold: e.isActive("bold"),
        italic: e.isActive("italic"),
        strike: e.isActive("strike"),
        subscript: e.isActive("subscript"),
        superscript: e.isActive("superscript"),
        link: e.isActive("link"),
        bullet: e.isActive("bullet_list"),
        ordered: e.isActive("ordered_list"),
        block: e.isActive("heading") ? `h${String(level ?? 2)}` : "p",
        align: (e.getAttributes(block).align as Align | null) ?? "left",
        font: view.font,
        size: view.size,
        color: style.color ?? "",
        highlight: (e.getAttributes("highlight").color as string | undefined) ?? "",
      };
    },
  });
  const tool = (name: Tool, label: ReactNode, run: () => void, pressed?: boolean, off?: boolean) => (
    <button
      type="button"
      className={editorStyles.tool}
      title={t(`editor.tools.${name}`)}
      aria-label={t(`editor.tools.${name}`)}
      {...(pressed === undefined ? {} : { "aria-pressed": pressed })}
      disabled={disabled || off}
      onMouseDown={(event) => {
        event.preventDefault(); // keeps the selection in the page
      }}
      onClick={run}
    >
      {label}
    </button>
  );
  const sizes: number[] = [...SIZES];
  if (state.size !== null && !sizes.includes(state.size)) {
    sizes.push(state.size);
    sizes.sort((a, b) => a - b);
  }
  return (
    <div className={editorStyles.ribbon} role="toolbar" aria-label={t("editor.ribbon")}>
      <div className={editorStyles.group}>
        {tool("undo", "↶", () => editor.chain().focus().undo().run(), undefined, !state.canUndo)}
        {tool("redo", "↷", () => editor.chain().focus().redo().run(), undefined, !state.canRedo)}
      </div>
      <div className={editorStyles.group}>
        {tool(
          "cut",
          "✂",
          () => {
            copySelection(editor).then(() => editor.chain().focus().deleteSelection().run(), onClipboardRefused);
          },
          undefined,
          state.empty,
        )}
        {tool(
          "copy",
          "⧉",
          () => {
            copySelection(editor).catch(onClipboardRefused);
          },
          undefined,
          state.empty,
        )}
        {tool("paste", "📋", () => {
          navigator.clipboard
            .read()
            .then(async (items) => {
              for (const item of items) {
                if (item.types.includes("text/html")) {
                  editor.view.pasteHTML(await (await item.getType("text/html")).text());
                  return;
                }
                if (item.types.includes("text/plain")) {
                  editor.view.pasteText(await (await item.getType("text/plain")).text());
                  return;
                }
              }
            })
            .catch(onClipboardRefused);
        })}
      </div>
      <div className={editorStyles.group}>
        <select
          className={editorStyles.select}
          aria-label={t("editor.tools.block")}
          disabled={disabled}
          value={state.block}
          onChange={(event) => {
            const value = event.target.value;
            const align = state.align === "left" ? null : state.align;
            if (value === "p") {
              editor.chain().focus().setNode("paragraph", { align }).run();
            } else {
              editor.chain().focus().setNode("heading", { level: Number(value.slice(1)), align }).run();
            }
          }}
        >
          <option value="p">{t("editor.blocks.p")}</option>
          <option value="h2">{t("editor.blocks.h2")}</option>
          <option value="h3">{t("editor.blocks.h3")}</option>
          <option value="h4">{t("editor.blocks.h4")}</option>
        </select>
        <select
          className={editorStyles.select}
          aria-label={t("editor.tools.font")}
          disabled={disabled}
          value={state.font}
          onChange={(event) => {
            setStyle(editor, "font", event.target.value || null);
          }}
        >
          <option value="">{t("editor.tools.font")}</option>
          {FONT_KEYS.map((key) => (
            <option key={key} value={key} style={{ fontFamily: FONTS[key].css }}>
              {FONTS[key].label}
            </option>
          ))}
        </select>
        <select
          className={editorStyles.size}
          aria-label={t("editor.tools.size")}
          disabled={disabled}
          value={state.size === null ? "" : String(state.size)}
          onChange={(event) => {
            setStyle(editor, "size", event.target.value ? Number(event.target.value) : null);
          }}
        >
          <option value="">{t("editor.tools.size")}</option>
          {sizes.map((size) => (
            <option key={size} value={size} disabled={!(SIZES as readonly number[]).includes(size)}>
              {size}
            </option>
          ))}
        </select>
      </div>
      <div className={editorStyles.group}>
        {tool("bold", <strong>G</strong>, () => editor.chain().focus().toggleMark("bold").run(), state.bold)}
        {tool("italic", <em>I</em>, () => editor.chain().focus().toggleMark("italic").run(), state.italic)}
        {tool("strike", <s>S</s>, () => editor.chain().focus().toggleMark("strike").run(), state.strike)}
        {tool(
          "subscript",
          <span>
            x<sub>2</sub>
          </span>,
          () => editor.chain().focus().toggleMark("subscript").run(),
          state.subscript,
        )}
        {tool(
          "superscript",
          <span>
            x<sup>2</sup>
          </span>,
          () => editor.chain().focus().toggleMark("superscript").run(),
          state.superscript,
        )}
        <Palette
          label={t("editor.tools.color")}
          value={state.color}
          colors={COLORS}
          none={t("editor.defaultColor")}
          highlight={false}
          disabled={disabled}
          onPick={(color) => {
            setStyle(editor, "color", color);
          }}
        />
        <Palette
          label={t("editor.tools.highlight")}
          value={state.highlight}
          colors={HIGHLIGHTS}
          none={t("editor.noHighlight")}
          highlight
          disabled={disabled}
          onPick={(color) => {
            const chain = editor.chain().focus();
            (color ? chain.setMark("highlight", { color }) : chain.unsetMark("highlight")).run();
          }}
        />
      </div>
      <div className={editorStyles.group}>
        {ALIGNS.map((align) =>
          tool(
            align,
            ICONS[align],
            () => {
              const value = align === "left" ? null : align;
              editor.chain().focus().updateAttributes("paragraph", { align: value }).updateAttributes("heading", { align: value }).run();
            },
            state.align === align,
          ),
        )}
      </div>
      <div className={editorStyles.group}>
        {tool("bullet", "•", () => editor.chain().focus().toggleList("bullet_list", "list_item").run(), state.bullet)}
        {tool("ordered", "1.", () => editor.chain().focus().toggleList("ordered_list", "list_item").run(), state.ordered)}
        {tool(
          "link",
          "🔗",
          () => {
            const current = (editor.getAttributes("link").href as string | undefined) ?? "https://";
            const href = window.prompt(t("editor.linkPrompt"), current);
            if (href === null) {
              return;
            }
            const chain = editor.chain().focus().extendMarkRange("link");
            if (href.trim() === "") {
              chain.unsetMark("link").run();
            } else if (SAFE_LINK.test(href.trim())) {
              chain.setMark("link", { href: href.trim() }).run();
            } else {
              window.alert(t("editor.linkInvalid"));
            }
          },
          state.link,
        )}
        <button
          type="button"
          className={editorStyles.tool}
          title={t("editor.tools.image")}
          aria-label={t("editor.tools.image")}
          disabled={disabled}
          onMouseDown={(event) => {
            event.preventDefault();
          }}
          onClick={() => {
            picker.current?.click();
          }}
        >
          🖼
        </button>
        <input
          ref={picker}
          type="file"
          accept={IMAGE_TYPES.join(",")}
          multiple
          hidden
          onChange={(event) => {
            onImages(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
        {tool("separator", "―", () => editor.chain().focus().insertContent({ type: "separateur" }).run())}
        {tool("clear", "⌫", () => {
          const chain = editor.chain().focus();
          PRESENTATION.forEach((mark) => chain.unsetMark(mark));
          chain.setNode("paragraph", { align: null }).run();
        })}
      </div>
    </div>
  );
}
