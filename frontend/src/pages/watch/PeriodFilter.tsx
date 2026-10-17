// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ANY_TIME, type Period } from "../../triage.ts";
import { styles } from "./styles.ts";

type Choice = "any" | "today" | "week" | "month" | "custom";
const CHOICES: readonly Choice[] = ["any", "today", "week", "month", "custom"];

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** The bounds of a choice, in the user's own time zone: a week starts on Monday. */
function boundsOf(choice: Choice, from: string, to: string): Period {
  const today = startOfDay(new Date());
  switch (choice) {
    case "today":
      return { since: today.toISOString(), until: null };
    case "week": {
      const monday = new Date(today);
      monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
      return { since: monday.toISOString(), until: null };
    }
    case "month":
      return { since: new Date(today.getFullYear(), today.getMonth(), 1).toISOString(), until: null };
    case "custom": {
      // <input type="date"> gives YYYY-MM-DD; the last day is included.
      const since = from === "" ? null : new Date(`${from}T00:00:00`);
      const until = to === "" ? null : new Date(`${to}T00:00:00`);
      until?.setDate(until.getDate() + 1);
      return { since: since?.toISOString() ?? null, until: until?.toISOString() ?? null };
    }
    default:
      return ANY_TIME;
  }
}

/** Narrows the feed and the search to a period (I1): today, this week, this month, or two
 * chosen days, both included. */
export function PeriodFilter({ onChange }: { onChange: (period: Period) => void }) {
  const { t } = useTranslation();
  const [choice, setChoice] = useState<Choice>("any");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const inverted = choice === "custom" && from !== "" && to !== "" && to < from;
  const apply = (next: Choice, nextFrom: string, nextTo: string) => {
    setChoice(next);
    setFrom(nextFrom);
    setTo(nextTo);
    if (!(next === "custom" && nextFrom !== "" && nextTo !== "" && nextTo < nextFrom)) {
      onChange(boundsOf(next, nextFrom, nextTo));
    }
  };
  return (
    <div className={styles.periodFilter}>
      <div className={styles.field}>
        <label htmlFor="period-filter">{t("triage.period.label")}</label>
        <select
          id="period-filter"
          value={choice}
          onChange={(event) => {
            apply(event.target.value as Choice, from, to);
          }}
        >
          {CHOICES.map((option) => (
            <option key={option} value={option}>
              {t(`triage.period.${option}`)}
            </option>
          ))}
        </select>
      </div>
      {choice === "custom" && (
        <>
          <div className={styles.field}>
            <label htmlFor="period-from">{t("triage.period.from")}</label>
            <input
              id="period-from"
              type="date"
              value={from}
              onChange={(event) => {
                apply("custom", event.target.value, to);
              }}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="period-to">{t("triage.period.to")}</label>
            <input
              id="period-to"
              type="date"
              value={to}
              onChange={(event) => {
                apply("custom", from, event.target.value);
              }}
            />
          </div>
          {inverted && (
            <p role="alert" className={styles.error}>
              {t("triage.period.inverted")}
            </p>
          )}
        </>
      )}
    </div>
  );
}
