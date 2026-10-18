// SPDX-License-Identifier: AGPL-3.0-or-later
import type { Editor } from "@tiptap/core";
import { Gapcursor, UndoRedo } from "@tiptap/extensions";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import { useBlocker } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { toDocument } from "../../editor/document.ts";
import { COLORS, FONT_KEYS, FONTS, HIGHLIGHTS, SIZES, type TextStyle } from "../../editor/format.ts";
import { cleanPastedHtml } from "../../editor/paste.ts";
import { extensions, type Source } from "../../editor/schema.ts";
import { editorStyles } from "../../editor/styles.ts";
import { useSaveVersion, type VersionView } from "../../writing.ts";
import { errorText } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

const SAFE_LINK = /^(https?:\/\/|mailto:)[^\s<>"]+$/i;
const PRESENTATION = ["bold", "italic", "strike", "highlight", "text_style"] as const;

type Tool =
  | "undo"
  | "redo"
  | "cut"
  | "copy"
  | "paste"
  | "bold"
  | "italic"
  | "strike"
  | "bullet"
  | "ordered"
  | "link"
  | "separator"
  | "clear";

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

function Ribbon({ editor, onClipboardRefused }: { editor: Editor; onClipboardRefused: () => void }) {
  const { t } = useTranslation();
  const state = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      const style = e.getAttributes("text_style") as TextStyle;
      const level = e.getAttributes("heading").level as number | undefined;
      return {
        canUndo: e.can().undo(),
        canRedo: e.can().redo(),
        empty: e.state.selection.empty,
        bold: e.isActive("bold"),
        italic: e.isActive("italic"),
        strike: e.isActive("strike"),
        link: e.isActive("link"),
        bullet: e.isActive("bullet_list"),
        ordered: e.isActive("ordered_list"),
        block: e.isActive("heading") ? `h${String(level ?? 2)}` : "p",
        font: style.font ?? "",
        size: style.size ? String(style.size) : "",
        color: style.color ?? "",
        highlight: (e.getAttributes("highlight").color as string | undefined) ?? "",
      };
    },
  });
  const tool = (name: Tool, label: string, run: () => void, pressed?: boolean, disabled?: boolean) => (
    <button
      type="button"
      className={editorStyles.tool}
      title={t(`editor.tools.${name}`)}
      aria-label={t(`editor.tools.${name}`)}
      {...(pressed === undefined ? {} : { "aria-pressed": pressed })}
      disabled={disabled}
      onMouseDown={(event) => {
        event.preventDefault(); // keeps the selection in the page
      }}
      onClick={run}
    >
      {label}
    </button>
  );
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
            copySelection(editor).then(
              () => editor.chain().focus().deleteSelection().run(),
              onClipboardRefused,
            );
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
          value={state.block}
          onChange={(event) => {
            const value = event.target.value;
            if (value === "p") {
              editor.chain().focus().setNode("paragraph").run();
            } else {
              editor.chain().focus().setNode("heading", { level: Number(value.slice(1)) }).run();
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
          value={state.font}
          onChange={(event) => {
            setStyle(editor, "font", event.target.value || null);
          }}
        >
          <option value="">{t("editor.defaultFont")}</option>
          {FONT_KEYS.map((key) => (
            <option key={key} value={key} style={{ fontFamily: FONTS[key].css }}>
              {FONTS[key].label}
            </option>
          ))}
        </select>
        <select
          className={editorStyles.select}
          aria-label={t("editor.tools.size")}
          value={state.size}
          onChange={(event) => {
            setStyle(editor, "size", event.target.value ? Number(event.target.value) : null);
          }}
        >
          <option value="">{t("editor.defaultSize")}</option>
          {SIZES.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>
      <div className={editorStyles.group}>
        {tool("bold", "G", () => editor.chain().focus().toggleMark("bold").run(), state.bold)}
        {tool("italic", "I", () => editor.chain().focus().toggleMark("italic").run(), state.italic)}
        {tool("strike", "S̶", () => editor.chain().focus().toggleMark("strike").run(), state.strike)}
        <select
          className={editorStyles.select}
          aria-label={t("editor.tools.color")}
          value={state.color}
          onChange={(event) => {
            setStyle(editor, "color", event.target.value || null);
          }}
        >
          <option value="">{t("editor.defaultColor")}</option>
          {COLORS.map(([value, name]) => (
            <option key={value} value={value} style={{ color: value === "#ffffff" ? "#595959" : value }}>
              {name}
            </option>
          ))}
        </select>
        <select
          className={editorStyles.select}
          aria-label={t("editor.tools.highlight")}
          value={state.highlight}
          onChange={(event) => {
            const color = event.target.value;
            const chain = editor.chain().focus();
            (color ? chain.setMark("highlight", { color }) : chain.unsetMark("highlight")).run();
          }}
        >
          <option value="">{t("editor.noHighlight")}</option>
          {HIGHLIGHTS.map(([value, name]) => (
            <option key={value} value={value} style={{ backgroundColor: value }}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div className={editorStyles.group}>
        {tool(
          "bullet",
          "•",
          () => editor.chain().focus().toggleList("bullet_list", "list_item").run(),
          state.bullet,
        )}
        {tool(
          "ordered",
          "1.",
          () => editor.chain().focus().toggleList("ordered_list", "list_item").run(),
          state.ordered,
        )}
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
        {tool("separator", "―", () => editor.chain().focus().insertContent({ type: "separateur" }).run())}
        {tool("clear", "⌫", () => {
          const chain = editor.chain().focus();
          PRESENTATION.forEach((mark) => chain.unsetMark(mark));
          chain.setNode("paragraph").run();
        })}
      </div>
    </div>
  );
}

/** The editor of a version (X03, ADR-0036): « Enregistrer » updates a person's version, or adds
 * it when the version is the model's; « Enregistrer comme nouvelle version » always adds one. */
export function VersionEditor({
  workspaceId,
  briefId,
  articleId,
  version,
  onSaved,
  onClose,
}: {
  workspaceId: string;
  briefId: string;
  articleId: string;
  version: VersionView;
  onSaved: (number: number) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [current, setCurrent] = useState(version);
  const [title, setTitle] = useState(version.title);
  const [dirty, setDirty] = useState(false);
  const [clipboardRefused, setClipboardRefused] = useState(false);
  const save = useSaveVersion(workspaceId, briefId);
  const attrs = version.document.attrs as Record<string, unknown>;
  const sources = (attrs.sources ?? []) as Source[];
  const editor = useEditor({
    extensions: [...extensions(sources), UndoRedo, Gapcursor],
    content: version.document,
    editorProps: {
      transformPastedHTML: (html) => cleanPastedHtml(html, sources),
      attributes: { class: editorStyles.page, "aria-label": t("editor.page") },
    },
    onUpdate: () => {
      setDirty(true);
    },
  });
  useBlocker({
    shouldBlockFn: () => dirty && !window.confirm(t("editor.leave")),
    enableBeforeUnload: () => dirty,
  });
  const submit = (asNew: boolean) => {
    save.mutate(
      {
        articleId,
        number: current.number,
        body: {
          title,
          document: toDocument(editor.getJSON(), attrs),
          updated_at: current.updated_at,
          as_new: asNew,
        },
      },
      {
        onSuccess: (saved) => {
          setCurrent(saved);
          setDirty(false);
          onSaved(saved.number);
        },
      },
    );
  };
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  return (
    <div className={editorStyles.editor}>
      <Ribbon
        editor={editor}
        onClipboardRefused={() => {
          setClipboardRefused(true);
        }}
      />
      <input
        className={editorStyles.title}
        aria-label={t("editor.title")}
        value={title}
        onChange={(event) => {
          setTitle(event.target.value);
          setDirty(true);
        }}
      />
      <EditorContent editor={editor} />
      <div className={editorStyles.bar}>
        <button
          type="button"
          className={styles.primary}
          disabled={save.isPending || title.trim() === ""}
          onClick={() => {
            submit(false);
          }}
        >
          {t("editor.save")}
        </button>
        <button
          type="button"
          className={styles.button}
          disabled={save.isPending || title.trim() === ""}
          onClick={() => {
            submit(true);
          }}
        >
          {t("editor.saveAsNew")}
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={() => {
            if (!dirty || window.confirm(t("editor.leave"))) {
              setDirty(false);
              onClose();
            }
          }}
        >
          {t("editor.close")}
        </button>
        <span role="status" className={styles.meta}>
          {save.isPending
            ? t("editor.saving")
            : dirty
              ? t("editor.unsaved")
              : current.origin === "ia"
                ? t("editor.modelVersion", { number: current.number })
                : t("editor.saved", { number: current.number })}
        </span>
      </div>
      {conflict && (
        <p role="alert" className={styles.error}>
          {t("editor.conflict")}
        </p>
      )}
      {save.error !== null && !conflict && (
        <p role="alert" className={styles.error}>
          {errorText(t, save.error)}
        </p>
      )}
      {clipboardRefused && (
        <p role="note" className={styles.notice}>
          {t("editor.clipboardRefused")}
        </p>
      )}
    </div>
  );
}
