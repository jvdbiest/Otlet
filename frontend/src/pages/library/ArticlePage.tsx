// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { workspacesQuery } from "../../session.ts";
import { articleQuery, useArchiveArticle, useSendArticle, useSetTags, type ArticleView } from "../../writing.ts";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { ArticleVersions } from "../writing/ArticleVersions.tsx";
import { Warning } from "../writing/Warning.tsx";

function Tags({ workspaceId, article }: { workspaceId: string; article: ArticleView }) {
  const { t } = useTranslation();
  const setTags = useSetTags(workspaceId);
  const [typed, setTyped] = useState(article.tags.join(", "));
  return (
    <form
      className={styles.row}
      onSubmit={(event) => {
        event.preventDefault();
        setTags.mutate({ articleId: article.id, tags: typed.split(",") });
      }}
    >
      <label>
        {t("library.tags")}{" "}
        <input
          value={typed}
          placeholder={t("library.tagsPlaceholder")}
          onChange={(event) => {
            setTyped(event.target.value);
          }}
        />
      </label>
      <button type="submit" className={styles.button} disabled={setTags.isPending}>
        {t("library.saveTags")}
      </button>
      {setTags.error !== null && (
        <span role="alert" className={styles.error}>
          {errorText(t, setTags.error)}
        </span>
      )}
    </form>
  );
}

/** An article of the Library (X04): its validated and current versions, its tags, the same
 * editor as in the workshop. */
export function ArticlePage({ articleId }: { articleId: string }) {
  const { t } = useTranslation();
  const workspaces = useQuery(workspacesQuery);
  const workspaceId = workspaces.data?.[0]?.id ?? "";
  const article = useQuery({ ...articleQuery(workspaceId, articleId), enabled: workspaceId !== "" });
  const send = useSendArticle(workspaceId);
  const archive = useArchiveArticle(workspaceId);
  const [chosen, setChosen] = useState<number | null>(null);
  if (article.error !== null) {
    return <p role="alert">{errorText(t, article.error)}</p>;
  }
  if (article.data === undefined) {
    return null;
  }
  const data = article.data;
  const current = data.versions.at(-1);
  const validated = data.versions.find((v) => v.number === data.validated_version);
  const ahead = validated !== undefined && current !== undefined && current.number > validated.number;
  return (
    <section>
      <p>
        <Link to="/bibliotheque">{t("library.back")}</Link>
      </p>
      <h1>{data.title}</h1>
      <p className={styles.row}>
        <span className={styles.badge}>{t(`library.status.${data.status}`)}</span>
        {validated !== undefined && (
          <span>{t("library.validated", { number: validated.number, date: formatDate(validated.updated_at) })}</span>
        )}
        {ahead && <span>{t("library.current", { number: current.number })}</span>}
      </p>
      {ahead && (
        <div>
          <Warning
            text={t("library.aheadWarning", {
              count: current.number - validated.number,
              from: validated.number + 1,
              to: current.number,
              validated: validated.number,
            })}
          />
          <p className={styles.row}>
            <button
              type="button"
              className={styles.primary}
              disabled={send.isPending}
              onClick={() => {
                send.mutate({ articleId: data.id, number: current.number });
              }}
            >
              {t("library.validateThis", { number: current.number })}
            </button>
          </p>
        </div>
      )}
      <Tags key={data.tags.join("|")} workspaceId={workspaceId} article={data} />
      <p className={styles.row}>
        {data.brief_id !== null && (
          <Link to="/redaction/briefs/$briefId" params={{ briefId: data.brief_id }} className={styles.button}>
            {t("library.openBrief")}
          </Link>
        )}
        <button
          type="button"
          className={styles.button}
          disabled={archive.isPending}
          onClick={() => {
            archive.mutate({ articleId: data.id, archived: data.status !== "archive" });
          }}
        >
          {data.status === "archive" ? t("library.unarchive") : t("library.archive")}
        </button>
      </p>
      <section className={styles.panel} aria-labelledby="draft-title">
        <h2 id="draft-title">{t("library.versions")}</h2>
        <ArticleVersions
          key={data.id}
          workspaceId={workspaceId}
          article={data}
          chosen={chosen ?? data.validated_version}
          onChoose={setChosen}
          actions={(shown) =>
            shown.number !== data.validated_version ? (
              <button
                type="button"
                className={styles.button}
                disabled={send.isPending}
                onClick={() => {
                  send.mutate({ articleId: data.id, number: shown.number });
                }}
              >
                {t("library.validateThis", { number: shown.number })}
              </button>
            ) : (
              <span className={styles.meta}>{t("library.isValidated")}</span>
            )
          }
        />
      </section>
    </section>
  );
}
