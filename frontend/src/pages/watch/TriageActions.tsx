// SPDX-License-Identifier: AGPL-3.0-or-later
import { Button } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { useChangeTriage, type TriageView } from "../../triage.ts";
import { styles } from "./styles.ts";

/** Keep, dismiss, archive, pin an item (X02, F-VEI-05); each decision can be undone. The flow
 * of an item: to sort, kept, (drafting, from I2), archived. */
export function TriageActions({
  workspaceId,
  itemId,
  title,
  triage,
  showUnread = false,
}: {
  workspaceId: string;
  itemId: string;
  title: string;
  triage: TriageView;
  showUnread?: boolean;
}) {
  const { t } = useTranslation();
  const change = useChangeTriage(workspaceId);
  const busy = change.isPending;
  const send = (body: Parameters<typeof change.mutate>[0]["change"]) => {
    change.mutate({ itemId, change: body });
  };
  return (
    <div className={styles.row} role="group" aria-label={t("triage.actions", { title })}>
      {triage.decision === "kept" && <span className={styles.good}>{t("triage.kept")}</span>}
      {triage.decision === "dismissed" && <span className={styles.neutral}>{t("triage.dismissed")}</span>}
      {triage.decision === "archived" && <span className={styles.neutral}>{t("triage.archived")}</span>}
      {triage.pinned && <span className={styles.limited}>{t("triage.pinned")}</span>}
      {triage.decision === null ? (
        <>
          <Button
            className={styles.button}
            isDisabled={busy}
            onPress={() => {
              send({ decision: "kept" });
            }}
          >
            {t("triage.keep")}
          </Button>
          <Button
            className={styles.button}
            isDisabled={busy}
            onPress={() => {
              send({ decision: "dismissed" });
            }}
          >
            {t("triage.dismiss")}
          </Button>
        </>
      ) : (
        <>
          {triage.decision === "kept" && (
            <Button
              className={styles.button}
              isDisabled={busy}
              onPress={() => {
                send({ decision: "archived" });
              }}
            >
              {t("triage.archive")}
            </Button>
          )}
          <Button
            className={styles.button}
            isDisabled={busy}
            onPress={() => {
              send({ decision: null });
            }}
          >
            {t("triage.undo")}
          </Button>
        </>
      )}
      <Button
        className={styles.button}
        isDisabled={busy}
        onPress={() => {
          send({ pinned: !triage.pinned });
        }}
      >
        {triage.pinned ? t("triage.unpin") : t("triage.pin")}
      </Button>
      {showUnread && triage.read_at !== null && (
        <Button
          className={styles.button}
          isDisabled={busy}
          onPress={() => {
            send({ read: false });
          }}
        >
          {t("triage.markUnread")}
        </Button>
      )}
      {change.error !== null && (
        <span role="alert" className={styles.error}>
          {t("triage.failed")}
        </span>
      )}
    </div>
  );
}
