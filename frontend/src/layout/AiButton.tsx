// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ButtonHTMLAttributes } from "react";
import { useTranslation } from "react-i18next";
import css from "./AiButton.module.css";

const styles = css as Record<"running", string>;

/** The button of everything that calls a model (Joël, 2026-10-30): while the work runs it is
 * bright blue, its colour moving from left to right, and it cancels that work. */
export function AiButton({
  running,
  onCancel,
  cancelling = false,
  children,
  ...button
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  running: boolean;
  onCancel: () => void;
  cancelling?: boolean;
}) {
  const { t } = useTranslation();
  return running ? (
    <button type="button" className={styles.running} disabled={cancelling} onClick={onCancel}>
      {t("aiTasks.cancel")}
    </button>
  ) : (
    <button {...button}>{children}</button>
  );
}
