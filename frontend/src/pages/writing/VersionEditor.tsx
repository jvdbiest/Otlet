// SPDX-License-Identifier: AGPL-3.0-or-later
import { Gapcursor, UndoRedo } from "@tiptap/extensions";
import type { EditorView } from "@tiptap/pm/view";
import { EditorContent, useEditor } from "@tiptap/react";
import { useBlocker } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../api/client.ts";
import { toDocument } from "../../editor/document.ts";
import { cleanPastedHtml } from "../../editor/paste.ts";
import { extensions, type Source } from "../../editor/schema.ts";
import { imageView } from "../../editor/imageView.ts";
import { editorStyles } from "../../editor/styles.ts";
import { IMAGE_TYPES, mediaIdOf, mediaUrl, uploadImage } from "../../media.ts";
import { useDiscardVersion, useSaveVersion, type VersionView } from "../../writing.ts";
import { errorText } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { Ribbon } from "./Ribbon.tsx";
import { Warning } from "./Warning.tsx";

/** The editor of a version (X03, ADR-0036): « Enregistrer » updates a person's version, or adds
 * it when the version is the model's; « Enregistrer comme nouvelle version » always adds one. */
/** The words of the text being written, as the drafts count them (Joël, 2026-10-19). */
function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}

export function VersionEditor({
  workspaceId,
  articleId,
  version,
  copiedFrom,
  validated,
  onSaved,
  onClose,
}: {
  workspaceId: string;
  articleId: string;
  version: VersionView;
  copiedFrom: number | null; // the model's version this one was copied from on opening
  validated: number | null; // the article's validated version: saving it adds a version
  onSaved: (number: number, from: number) => void; // the version saved, the one edited
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [current, setCurrent] = useState(version);
  const [title, setTitle] = useState(version.title);
  const [dirty, setDirty] = useState(false);
  const [clipboardRefused, setClipboardRefused] = useState(false);
  const [inTitle, setInTitle] = useState(false);
  const [words, setWords] = useState(0);
  const save = useSaveVersion(workspaceId);
  const discard = useDiscardVersion(workspaceId);
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
  const [uploading, setUploading] = useState(0);
  const [uploadError, setUploadError] = useState<Error | null>(null);
  const media = {
    mediaUrl: (id: string) => mediaUrl(workspaceId, id),
    mediaIdOf,
    view: imageView((id) => mediaUrl(workspaceId, id), {
      size: (width) => t("editor.imageWidth", { width }),
      handle: t("editor.imageHandle"),
      own: t("editor.imageOwn"),
      wrap: t("editor.imageWrap"),
    }),
  };
  // Images sent one by one, each inserted where the cursor is once it is stored (X03b).
  const insertImages = (files: File[], insert: (media: string, alt: string) => void) => {
    const images = files.filter((file) => (IMAGE_TYPES as readonly string[]).includes(file.type));
    if (images.length === 0) {
      return false;
    }
    setUploadError(null);
    for (const file of images) {
      setUploading((n) => n + 1);
      uploadImage(workspaceId, file)
        .then((made) => {
          insert(made.id, "");
        })
        .catch((error: unknown) => {
          setUploadError(error instanceof Error ? error : new Error(String(error)));
        })
        .finally(() => {
          setUploading((n) => n - 1);
        });
    }
    return true;
  };
  // An image node put where the selection is, from the view the paste or drop happened in.
  const inView = (view: EditorView) => (media: string, alt: string) => {
    const node = view.state.schema.nodes.image?.create({ media, alt });
    if (node !== undefined) {
      view.dispatch(view.state.tr.replaceSelectionWith(node));
    }
  };
  const editor = useEditor({
    extensions: [...extensions(sources, media), UndoRedo, Gapcursor],
    content: version.document,
    editorProps: {
      transformPastedHTML: (html) => cleanPastedHtml(html, sources),
      // An image copied from another application, or dropped on the page.
      handlePaste: (view, event) => insertImages(Array.from(event.clipboardData?.files ?? []), inView(view)),
      handleDrop: (view, event) => insertImages(Array.from(event.dataTransfer?.files ?? []), inView(view)),
      attributes: { class: editorStyles.page, "aria-label": t("editor.page") },
    },
    onCreate: ({ editor: created }) => {
      setWords(countWords(created.getText()));
    },
    onUpdate: ({ editor: changed }) => {
      setDirty(true);
      setWords(countWords(changed.getText()));
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
          onSaved(saved.number, current.number);
        },
      },
    );
  };
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  // The actions at the top as well as under the text (Joël, 2026-10-18): saving needs no
  // scrolling down.
  const actions = (
    <>
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
    </>
  );
  return (
    <div className={editorStyles.editor}>
      {copiedFrom !== null && <Warning text={t("editor.copied", { from: copiedFrom, number: version.number })} />}
      <div className={editorStyles.top}>
        <div className={editorStyles.actions}>
          {actions}
          <span role="status" className={styles.meta}>
              {save.isPending
                ? t("editor.saving")
                : dirty
                  ? t("editor.unsaved")
                  : current.origin === "ia"
                    ? t("editor.modelVersion", { number: current.number })
                    : current.number === validated
                      ? t("editor.validatedVersion", { number: current.number })
                    : t("editor.saved", { number: current.number })}
              {" · "}
              {t("watch.words", { count: words })}
            </span>
        </div>
        <Ribbon
          editor={editor}
          disabled={inTitle}
          onImages={(files) => {
            insertImages(files, (media, alt) => {
              editor.chain().focus().insertContent({ type: "image", attrs: { media, alt } }).run();
            });
          }}
          onClipboardRefused={() => {
            setClipboardRefused(true);
          }}
        />
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
      <div className={editorStyles.bar}>{actions}</div>
      {uploading > 0 && (
        <p role="status" className={styles.meta}>
          {t("editor.uploading", { count: uploading })}
        </p>
      )}
      {uploadError !== null && (
        <p role="alert" className={styles.error}>
          {errorText(t, uploadError)}
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
