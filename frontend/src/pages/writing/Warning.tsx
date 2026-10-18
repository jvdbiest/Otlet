// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";

/** An « Avertissement » about the version shown, with what it names: a link to the block
 * when the text can find it. */
export function Warning({ text, items }: { text: string; items?: { label: string; anchor?: string | undefined }[] }) {
  const { t } = useTranslation();
  return (
    <div role="note" className={styles.warning}>
      <p>
        <strong>{t("draft.warning")}</strong>
      </p>
      <p>{text}</p>
      {items !== undefined && (
        <ul>
          {items.map((item, index) => (
            <li key={index}>{item.anchor ? <a href={`#${item.anchor}`}>{item.label}</a> : item.label}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
