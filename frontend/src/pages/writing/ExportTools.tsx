// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";

const FORMATS = ["pdf", "docx", "html", "md", "txt"] as const;

/** Print and export a version (X03c): files made by the server from the saved version. */
export function ExportTools({ workspaceId, articleId, number }: { workspaceId: string; articleId: string; number: number }) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState(false);
  const url = (kind: string) =>
    `/api/workspaces/${encodeURIComponent(workspaceId)}/articles/${encodeURIComponent(articleId)}/versions/${String(number)}/export/${kind}`;
  return (
    <>
      <button
        type="button"
        className={styles.button}
        onClick={() => {
          setFailed(false);
          fetch(url("html"), { credentials: "same-origin" })
            .then((response) => (response.ok ? response.text() : Promise.reject(new Error(String(response.status)))))
            .then((page) => {
              // The export page in a hidden frame, printed from there: the browser's print dialog
              // offers « Enregistrer au format PDF » too.
              const frame = document.createElement("iframe");
              frame.style.position = "fixed";
              frame.style.width = "0";
              frame.style.height = "0";
              frame.style.border = "0";
              frame.addEventListener("load", () => {
                frame.contentWindow?.focus();
                frame.contentWindow?.print();
                window.setTimeout(() => {
                  frame.remove();
                }, 60_000);
              });
              frame.srcdoc = page;
              document.body.append(frame);
            })
            .catch(() => {
              setFailed(true);
            });
        }}
      >
        {t("draft.print")}
      </button>
      <select
        aria-label={t("draft.export")}
        className={styles.button}
        value=""
        onChange={(event) => {
          const kind = event.target.value;
          if (kind) {
            window.location.assign(url(kind));
          }
        }}
      >
        <option value="">{t("draft.export")}</option>
        {FORMATS.map((kind) => (
          <option key={kind} value={kind}>
            {t(`draft.formats.${kind}`)}
          </option>
        ))}
      </select>
      {failed && (
        <span role="alert" className={styles.error}>
          {t("draft.printFailed")}
        </span>
      )}
    </>
  );
}
