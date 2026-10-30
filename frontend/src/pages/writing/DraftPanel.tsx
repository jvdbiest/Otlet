// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  draftQuery,
  useCancelGeneration,
  useClearDetails,
  useGenerateDraft,
  type GenerationView,
} from "../../writing.ts";
import { ApiError } from "../../api/client.ts";
import { AiButton } from "../../layout/AiButton.tsx";
import { errorText, formatDate } from "../watch/labels.ts";
import { styles } from "../watch/styles.ts";
import { ArticleVersions } from "./ArticleVersions.tsx";
import { GenerationDetails } from "./GenerationDetails.tsx";
import { LibraryActions } from "./LibraryActions.tsx";

const FAILURES = [
  "no_profile",
  "no_sources",
  "budget",
  "refused",
  "invalid",
  "out_of_room",
  "quota",
  "unavailable",
  "blocked",
  "cancelled",
] as const;

function failure(generation: GenerationView): (typeof FAILURES)[number] {
  return FAILURES.find((code) => code === generation.error) ?? "unavailable";
}

/** The draft of a brief (U04): generate it, follow the generation, read its versions. */
export function DraftPanel({ workspaceId, briefId }: { workspaceId: string; briefId: string }) {
  const { t } = useTranslation();
  const draft = useQuery(draftQuery(workspaceId, briefId));
  const generate = useGenerateDraft(workspaceId, briefId);
  const cancel = useCancelGeneration(workspaceId, briefId);
  const clear = useClearDetails(workspaceId, briefId);
  const [confirming, setConfirming] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  if (draft.data === undefined) {
    return null;
  }
  const { article, generation } = draft.data;
  const running = generation?.status === "running";
  const versions = article?.versions ?? [];
  return (
    <section className={styles.panel} aria-labelledby="draft-title">
      <h2 id="draft-title">{t("draft.title")}</h2>
      <p className={styles.help}>{t("draft.help")}</p>
      <p className={styles.row}>
        <AiButton
          running={running}
          cancelling={cancel.isPending}
          onCancel={() => {
            cancel.mutate();
          }}
          type="button"
          className={styles.primary}
          disabled={generate.isPending}
          onClick={() => {
            generate.mutate(false, {
              onSuccess: () => {
                setChosen(null);
              },
            });
          }}
        >
          {versions.length === 0 ? t("draft.generate") : t("draft.again")}
        </AiButton>
        {running && (
          <span role="status" className={styles.meta}>
            {t("draft.running", { since: formatDate(generation.created_at) })}
          </span>
        )}
      </p>
      {generate.error instanceof ApiError && generate.error.detail === "insufficient_matter" ? (
        <div role="alert" className={styles.warning}>
          <p>{t("draft.insufficient")}</p>
          <p>
            <button
              type="button"
              className={styles.button}
              disabled={generate.isPending}
              onClick={() => {
                generate.mutate(true, {
                  onSuccess: () => {
                    setChosen(null);
                  },
                });
              }}
            >
              {t("draft.generateAnyway")}
            </button>
          </p>
        </div>
      ) : (
        generate.error !== null && (
          <p role="alert" className={styles.error}>
            {errorText(t, generate.error)}
          </p>
        )
      )}
      {generation?.status === "failed" && (
        <div role="alert" className={styles.warning}>
          <p>{t(`draft.failed.${failure(generation)}`)}</p>
          <ul className={styles.journal}>
            {generation.attempts.map((attempt, index) => (
              <li key={index}>
                {String(attempt.provider)} · {String(attempt.model)} · {String(attempt.result)} ·{" "}
                {String(attempt.seconds)} s
              </li>
            ))}
          </ul>
          <GenerationDetails
            details={generation.details}
            heading={t("draft.details.failedHeading", { date: formatDate(generation.created_at) })}
          />
        </div>
      )}
      {article !== null && (
        <ArticleVersions
          key={article.id}
          workspaceId={workspaceId}
          article={article}
          chosen={chosen}
          onChoose={setChosen}
          actions={(shown) => <LibraryActions workspaceId={workspaceId} article={article} number={shown.number} />}
        />
      )}
      {(versions.length > 0 || generation !== null) && (
        <p className={styles.row}>
          {confirming ? (
            <>
              <span>{t("draft.details.confirmClear")}</span>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  clear.mutate(undefined, {
                    onSuccess: () => {
                      setConfirming(false);
                    },
                  });
                }}
              >
                {t("draft.details.clear")}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => {
                  setConfirming(false);
                }}
              >
                {t("brief.cancel")}
              </button>
            </>
          ) : (
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => {
                setConfirming(true);
              }}
            >
              {t("draft.details.clearAll")}
            </button>
          )}
        </p>
      )}
    </section>
  );
}
