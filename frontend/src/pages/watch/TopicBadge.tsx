// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TopicTagView } from "../../triage.ts";
import { styles } from "./styles.ts";

/** The main topic of an item, as a badge above its title; "+N" shows the others (I1). The
 * main topic is the best score, or, while topics are chosen in the filter, the best of those. */
export function TopicBadge({ topics, chosen }: { topics: TopicTagView[]; chosen: string[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  // The server sends the best score first; a stable sort keeps that order inside each group.
  const ordered = [...topics].sort(
    (a, b) => Number(chosen.includes(b.id)) - Number(chosen.includes(a.id)),
  );
  const [main, ...others] = ordered;
  if (main === undefined) {
    return null;
  }
  return (
    <p className={styles.topicLine}>
      <span className={styles.topicBadge} title={t("triage.topicScore", { points: main.score })}>
        {main.name}
      </span>
      {others.length > 0 &&
        (open ? (
          others.map((topic) => (
            <span
              key={topic.id}
              className={`${styles.topicBadge} ${styles.topicOther}`}
              title={t("triage.topicScore", { points: topic.score })}
            >
              {topic.name}
            </span>
          ))
        ) : (
          <button
            type="button"
            className={styles.topicMore}
            aria-label={t("triage.otherTopics", {
              count: others.length,
              names: others.map((topic) => topic.name).join(", "),
            })}
            onClick={() => {
              setOpen(true);
            }}
          >
            +{others.length}
          </button>
        ))}
    </p>
  );
}
