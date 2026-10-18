// SPDX-License-Identifier: AGPL-3.0-or-later
import { Gapcursor, UndoRedo } from "@tiptap/extensions";
import { EditorContent, useEditor } from "@tiptap/react";
import { useBlocker } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { toDocument } from "../../editor/document.ts";
import { cleanPastedHtml } from "../../editor/paste.ts";
import { extensions, type Source } from "../../editor/schema.ts";
import { editorStyles } from "../../editor/styles.ts";
import { useDiscardVersion, useSaveVersion, type VersionView } from "../../writing.ts";
import { errorText } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { Ribbon } from "./Ribbon.tsx";
import { Warning } from "./Warning.tsx";

/** The editor of a version (X03, ADR-0036): « Enregistrer » updates a person's version, or adds
 * it when the version is the model's; « Enregistrer comme nouvelle version » always adds one. */
export function VersionEditor({
  workspaceId,
  briefId,
  articleId,
  version,
  copiedFrom,
  onSaved,
  onClose,
}: {
  workspaceId: string;
  briefId: string;
  articleId: string;
  version: VersionView;
  copiedFrom: number | null; // the model's version this one was copied from on opening
  onSaved: (number: number) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [current, setCurrent] = useState(version);
  const [title, setTitle] = useState(version.title);
  const [dirty, setDirty] = useState(false);
  const [clipboardRefused, setClipboardRefused] = useState(false);
  const [inTitle, setInTitle] = useState(false);
  const save = useSaveVersion(workspaceId, briefId);
  const discard = useDiscardVersion(workspaceId, briefId);
  // A copy made on opening and never saved: closed or left, it goes.
  const untouched = useRef(copiedFrom !== null);
  const discardCopy = () => {
    if (untouched.current) {
      untouched.current = false;
      discard.mutate({ articleId, number: version.number });
    }
  };
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
    shouldBlockFn: () => {
      if (dirty && !window.confirm(t("editor.leave"))) {
        return true;
      }
      discardCopy();
      return false;
    },
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
          untouched.current = false;
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
      {copiedFrom !== null && <Warning text={t("editor.copied", { from: copiedFrom, number: version.number })} />}
      <Ribbon
        editor={editor}
        disabled={inTitle}
        onClipboardRefused={() => {
          setClipboardRefused(true);
        }}
      />
      <input
        className={editorStyles.title}
        aria-label={t("editor.title")}
        aria-describedby="editor-title-help"
        value={title}
        onFocus={() => {
          setInTitle(true);
        }}
        onBlur={() => {
          setInTitle(false);
        }}
        onChange={(event) => {
          setTitle(event.target.value);
          setDirty(true);
        }}
      />
      <p id="editor-title-help" className={editorStyles.titleHelp}>
        {t("editor.titleHelp")}
      </p>
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
              discardCopy();
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
