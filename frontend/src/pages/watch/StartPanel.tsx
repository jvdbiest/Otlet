// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { progressQuery } from "../../triage.ts";
import { styles } from "./styles.ts";

const HIDDEN_KEY = "otlet.start.hidden";
const SOURCES_SUGGESTED = 3;

function remembered(): boolean {
  try {
    return window.localStorage.getItem(HIDDEN_KEY) === "1";
  } catch {
    return false;
  }
}

/** The first steps of FA §7.7 that I1 covers: sources, a topic, a first triage. Shown until
 * they are done, or until the user hides it; it reads the data, so it never lies. */
export function StartPanel({ workspaceId }: { workspaceId: string }) {
  const { t } = useTranslation();
  const progress = useQuery(progressQuery(workspaceId));
  const [hidden, setHidden] = useState(remembered);
  if (hidden || progress.data === undefined) {
    return null;
  }
  const steps = [
    {
      key: "sources",
      done: progress.data.sources >= SOURCES_SUGGESTED,
      text: t("start.sources", { count: progress.data.sources }),
      to: "/veille/sources" as const,
    },
    { key: "topic", done: progress.data.topics > 0, text: t("start.topic"), to: "/veille/sujets" as const },
    { key: "triage", done: progress.data.decisions > 0, text: t("start.triage"), to: null },
  ];
  if (steps.every((step) => step.done)) {
    return null;
  }
  return (
    <section className={styles.panel} aria-labelledby="start-title">
      <h2 id="start-title">{t("start.title")}</h2>
      <p className={styles.meta}>{t("start.intro")}</p>
      <ol className={styles.steps}>
        {steps.map((step) => (
          <li key={step.key}>
            <span className={step.done ? styles.good : styles.neutral}>
              {step.done ? t("start.done") : t("start.todo")}
            </span>{" "}
            {step.text}{" "}
            {!step.done && step.to !== null && <Link to={step.to}>{t("start.go")}</Link>}
          </li>
        ))}
      </ol>
      <Button
        className={styles.button}
        onPress={() => {
          try {
            window.localStorage.setItem(HIDDEN_KEY, "1");
          } catch {
            // Without storage, the panel simply comes back next time.
          }
          setHidden(true);
        }}
      >
        {t("start.hide")}
      </Button>
    </section>
  );
}
