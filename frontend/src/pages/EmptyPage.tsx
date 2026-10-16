// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import css from "./EmptyPage.module.css";

const styles = css as Record<"empty" | "headline" | "next" | "page", string>;

export type Section = "watch" | "writing" | "library" | "settings";

/** A section that has nothing to show yet: what will be there, and nothing more. */
export function EmptyPage({ section }: { section: Section }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title">{t(`pages.${section}.title`)}</h1>
      <div className={styles.empty}>
        <p className={styles.headline}>{t(`pages.${section}.empty`)}</p>
        <p className={styles.next}>{t(`pages.${section}.next`)}</p>
      </div>
    </section>
  );
}
