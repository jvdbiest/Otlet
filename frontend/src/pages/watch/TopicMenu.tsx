// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { topicsQuery } from "../../watch.ts";
import { matchesFilter } from "./labels.ts";
import { styles } from "./styles.ts";

/** Chooses topics to narrow the feed and the search: items of at least one of them, or of
 * every one (I1). The chosen topics stay visible as chips, each removable. */
export function TopicMenu({
  workspaceId,
  topicIds,
  allTopics,
  onChange,
}: {
  workspaceId: string;
  topicIds: string[];
  allTopics: boolean;
  onChange: (topicIds: string[], allTopics: boolean) => void;
}) {
  const { t } = useTranslation();
  const topics = useQuery(topicsQuery(workspaceId));
  const [query, setQuery] = useState("");
  const menu = useRef<HTMLDetailsElement>(null);
  // Like any menu, it closes on a click elsewhere or on Escape.
  useEffect(() => {
    const close = (event: Event) => {
      const details = menu.current;
      if (details?.open !== true) {
        return;
      }
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !details.contains(event.target as Node)) {
        details.open = false;
        if (event instanceof KeyboardEvent) {
          details.querySelector("summary")?.focus();
        }
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  if (topics.data === undefined || topics.data.length === 0) {
    return null;
  }
  const options = topics.data;
  const shown = query.trim() === "" ? options : options.filter((o) => matchesFilter(o.name, query));
  // A topic deleted since it was chosen is no longer offered nor shown.
  const chosen = options.filter((topic) => topicIds.includes(topic.id));
  return (
    <div className={styles.topicFilter}>
      <details ref={menu} className={styles.menu}>
        <summary className={styles.button}>
          {chosen.length === 0 ? t("triage.topics") : t("triage.topicsChosen", { count: chosen.length })}
        </summary>
        <div className={styles.menuPanel}>
          <input
            type="search"
            aria-label={t("triage.filterTopics")}
            placeholder={t("triage.filterTopics")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
          <fieldset className={styles.menuChoices}>
            <legend className="visually-hidden">{t("triage.topics")}</legend>
            {shown.map((topic) => (
              <label key={topic.id}>
                <input
                  type="checkbox"
                  checked={topicIds.includes(topic.id)}
                  onChange={(event) => {
                    onChange(
                      event.target.checked
                        ? [...topicIds, topic.id]
                        : topicIds.filter((current) => current !== topic.id),
                      allTopics,
                    );
                  }}
                />{" "}
                {topic.name}
              </label>
            ))}
            {shown.length === 0 && (
              <span className={styles.help}>{t("triage.noTopicMatch", { q: query.trim() })}</span>
            )}
          </fieldset>
          <label className={styles.check}>
            <input
              type="checkbox"
              checked={allTopics}
              onChange={(event) => {
                onChange(topicIds, event.target.checked);
              }}
            />{" "}
            {t("triage.allTopics")}
          </label>
        </div>
      </details>
      {chosen.length > 0 && (
        <ul className={styles.chips} aria-label={t("triage.topics")}>
          {chosen.map((topic) => (
            <li key={topic.id} className={styles.chip}>
              {topic.name}
              <button
                type="button"
                aria-label={t("triage.removeTopic", { name: topic.name })}
                onClick={() => {
                  onChange(
                    topicIds.filter((current) => current !== topic.id),
                    allTopics,
                  );
                }}
              >
                ×
              </button>
            </li>
          ))}
          {chosen.length > 1 && (
            <li className={styles.chipsMode}>{allTopics ? t("triage.modeAll") : t("triage.modeAny")}</li>
          )}
          <li>
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => {
                onChange([], allTopics);
              }}
            >
              {t("triage.clearTopics")}
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
