// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { sessionQuery } from "../../session.ts";
import { styles } from "../watch/styles.ts";

/** The sections of Réglages: the AI settings of each user, the sites articles are published
 * to (U07), and the backups of the instance, shown to its administrator only (ADR-0042). */
export function SettingsTabs() {
  const { t } = useTranslation();
  const session = useQuery(sessionQuery);
  const admin = session.data?.user.is_instance_admin === true;
  return (
    <nav aria-label={t("settings.tabs.label")} className={styles.tabs}>
      <ul>
        <li>
          <Link to="/reglages" className={styles.tab} activeOptions={{ exact: true }} activeProps={{ "aria-current": "page" }}>
            {t("settings.tabs.ai")}
          </Link>
        </li>
        <li>
          <Link to="/reglages/publication" className={styles.tab} activeProps={{ "aria-current": "page" }}>
            {t("settings.tabs.publishing")}
          </Link>
        </li>
        {admin && (
          <li>
            <Link to="/reglages/sauvegardes" className={styles.tab} activeProps={{ "aria-current": "page" }}>
              {t("settings.tabs.backups")}
            </Link>
          </li>
        )}
      </ul>
    </nav>
  );
}
