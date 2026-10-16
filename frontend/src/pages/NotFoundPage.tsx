// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import css from "./EmptyPage.module.css";

const styles = css as Record<"empty" | "headline" | "next" | "page", string>;

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <main className={styles.page}>
      <h1>{t("pages.notFound.title")}</h1>
      <Link to="/veille">{t("pages.notFound.back")}</Link>
    </main>
  );
}
