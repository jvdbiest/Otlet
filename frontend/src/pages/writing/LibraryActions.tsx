// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useSendArticle, type ArticleView } from "../../writing.ts";
import { errorText } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";

/** In the brief (the workshop): « Envoyer en Bibliothèque » validates the version shown; once the
 * article is there, « Valider cette version » validates another (X04, ADR-0037). */
export function LibraryActions({
  workspaceId,
  article,
  number,
}: {
  workspaceId: string;
  article: ArticleView;
  number: number;
}) {
  const { t } = useTranslation();
  const send = useSendArticle(workspaceId);
  const inLibrary = article.sent_at !== null;
  return (
    <>
      {(!inLibrary || article.validated_version !== number) && (
        <button
          type="button"
          className={inLibrary ? styles.button : styles.primary}
          disabled={send.isPending}
          onClick={() => {
            send.mutate({ articleId: article.id, number });
          }}
        >
          {inLibrary ? t("library.validateThis", { number }) : t("library.send")}
        </button>
      )}
      {inLibrary && (
        <Link to="/bibliotheque/articles/$articleId" params={{ articleId: article.id }} className={styles.meta}>
          {t("library.inLibrary", { number: article.validated_version ?? 0 })}
        </Link>
      )}
      {send.error !== null && (
        <span role="alert" className={styles.error}>
          {errorText(t, send.error)}
        </span>
      )}
    </>
  );
}
