// SPDX-License-Identifier: AGPL-3.0-or-later
import { Button } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { useRescoreTopic, type TopicView } from "../../watch.ts";
import { formatDate } from "./labels.ts";
import { styles } from "./styles.ts";

/** Whether the topic is being matched again, when it last was, and the button to ask (U02b). */
export function RescoreStatus({ workspaceId, topic }: { workspaceId: string; topic: TopicView }) {
  const { t } = useTranslation();
  const rescore = useRescoreTopic(workspaceId);
  const busy = topic.rescoring || rescore.isPending;
  return (
    <div className={styles.row}>
      <span role="status" className={styles.meta}>
        {busy
          ? t("topics.rescoring")
          : topic.rescored_at !== null && t("topics.rescoredAt", { date: formatDate(topic.rescored_at) })}
      </span>
      <Button
        className={styles.button}
        isDisabled={busy}
        onPress={() => {
          rescore.mutate(topic.id);
        }}
      >
        {t("topics.rescore")}
      </Button>
    </div>
  );
}
