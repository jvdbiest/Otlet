// SPDX-License-Identifier: AGPL-3.0-or-later
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import { Button } from "react-aria-components";
import { useTranslation } from "react-i18next";
import type { SessionView } from "../api/client.ts";
import { useLogout, workspacesQuery } from "../session.ts";
import css from "./AppLayout.module.css";

const styles = css as Record<
  "shell" | "header" | "brand" | "workspace" | "account" | "logout" | "nav" | "link" | "main",
  string
>;

const SECTIONS = [
  { to: "/veille", label: "nav.watch" },
  { to: "/redaction", label: "nav.writing" },
  { to: "/bibliotheque", label: "nav.library" },
  { to: "/reglages", label: "nav.settings" },
] as const;

/** The frame of every signed-in page: header, main navigation, content. */
export function AppLayout({ session }: { session: SessionView }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const logout = useLogout();
  const workspaces = useQuery(workspacesQuery);
  // É1 has a single workspace per user (ROADMAP §5.2).
  const workspace = workspaces.data?.[0];

  return (
    <div className={styles.shell}>
      <a href="#main" className="visually-hidden">
        {t("app.skipToContent")}
      </a>
      <header className={styles.header}>
        <span className={styles.brand}>{t("app.name")}</span>
        {workspace !== undefined && (
          <span className={styles.workspace}>{t("account.workspace", { name: workspace.name })}</span>
        )}
        <div className={styles.account} aria-label={t("account.menu", { name: session.user.display_name })}>
          <span>{session.user.display_name}</span>
          <Button
            className={styles.logout}
            isDisabled={logout.isPending}
            onPress={() => {
              logout.mutate(undefined, {
                onSuccess: () => {
                  void navigate({ to: "/connexion" });
                },
              });
            }}
          >
            {t("account.logout")}
          </Button>
        </div>
      </header>
      <nav aria-label={t("nav.label")} className={styles.nav}>
        <ul>
          {SECTIONS.map((section) => (
            <li key={section.to}>
              <Link to={section.to} className={styles.link} activeProps={{ "aria-current": "page" }}>
                {t(section.label)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <main id="main" className={styles.main} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
