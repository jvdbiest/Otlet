// SPDX-License-Identifier: AGPL-3.0-or-later
import { Link, Outlet } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";

const TABS = [
  { to: "/bibliotheque", label: "library.tabs.articles" },
  { to: "/bibliotheque/medias", label: "library.tabs.media" },
  { to: "/bibliotheque/archives", label: "library.tabs.archives" },
] as const;

/** The Library (X04): its articles, its media, its archives, each tab at its own address
 * (Joël, 2026-10-20): the life of a content shows, and the archives are not a mode of a page. */
export function LibraryLayout() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{t("library.title")}</h1>
      <nav aria-label={t("library.tabs.label")} className={styles.tabs}>
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
