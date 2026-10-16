// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link, Outlet } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { styles } from "./styles.ts";

const TABS = [
  { to: "/veille", label: "watch.tabs.items" },
  { to: "/veille/sources", label: "watch.tabs.sources" },
  { to: "/veille/saisie", label: "watch.tabs.manual" },
] as const;

/** The watch section: its items, its sources, and manual entry (U01). */
export function WatchLayout() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{t("pages.watch.title")}</h1>
      <nav aria-label={t("watch.tabs.label")} className={styles.tabs}>
        <ul>
          {TABS.map((tab) => (
            <li key={tab.to}>
              <Link
                to={tab.to}
                className={styles.tab}
                activeOptions={{ exact: true }}
                activeProps={{ "aria-current": "page" }}
              >
                {t(tab.label)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <Outlet />
    </section>
  );
}
