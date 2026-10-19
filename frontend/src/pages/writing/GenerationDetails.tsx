// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";

// What a draft was written with (Joël, 2026-10-17): to diagnose it without guessing. Never the
// text of the prompt nor of the answer.
interface Details {
  brief?: {
    mode?: string;
    length?: string;
    length_used?: string;
    language?: string;
    model?: string;
    angle?: string;
    instructions?: string;
    audience?: string;
    tone?: string;
    channel?: string;
  };
  prompt_version?: string;
  window_tokens?: number;
  local?: boolean;
  output_tokens?: number;
  source_room_chars?: number;
  sources?: { key: string; title: string; chars: number; sent: number; cut: boolean }[];
  refusals?: string[][];
  attempts?: { provider?: string; model?: string; result?: string; seconds?: number; tokens_in?: number; tokens_out?: number }[];
  context_overflow?: boolean;
  lone_sections?: string[];
  repeated_paragraphs?: string[];
  matter_words?: number;
  thin_matter?: boolean;
  unsupported?: { kind: string; text: string }[];
  copying?: { share?: number; passages?: unknown[] };
}

const NUMBER = new Intl.NumberFormat("fr-BE");

/** The details as plain text: shown, and copied as they are. */
function detailsText(raw: Record<string, unknown>, heading: string): string {
  const details = raw as Details;
  const brief = details.brief ?? {};
  const lines = [heading];
  lines.push(
    `Brief : mode ${brief.mode ?? "?"}, longueur ${brief.length ?? "?"}, langue ${brief.language ?? "?"}, modèle ${brief.model ?? "?"}`,
  );
  if (brief.angle) {
    lines.push(`Angle : ${brief.angle}`);
  }
  if (brief.instructions) {
    lines.push(`Consignes : ${brief.instructions}`);
  }
  if (brief.audience) {
    lines.push(`Public : ${brief.audience}`);
  }
  if (brief.tone) {
    lines.push(`Ton : ${brief.tone}`);
  }
  if (brief.channel) {
    lines.push(`Canal : ${brief.channel}`);
  }
  lines.push(
    `Fenêtre : ${NUMBER.format(details.window_tokens ?? 0)} jetons (${details.local ? "moteur local" : "en ligne"}) ; réponse prévue : ${NUMBER.format(details.output_tokens ?? 0)} jetons ; place pour les sources : ${NUMBER.format(details.source_room_chars ?? 0)} caractères ; consigne ${details.prompt_version ?? "?"}`,
  );
  for (const source of details.sources ?? []) {
    lines.push(
      `${source.key} « ${source.title} » : ${NUMBER.format(source.chars)} caractères, ${NUMBER.format(source.sent)} envoyés${source.cut ? " (raccourci)" : ""}`,
    );
  }
  (details.refusals ?? []).forEach((errors, index) => {
    lines.push(`Réponse ${String(index + 1)} refusée par Otlet : ${errors.join(" ; ")}`);
  });
  for (const attempt of details.attempts ?? []) {
    lines.push(
      `Appel : ${attempt.model ?? "?"} (${attempt.provider ?? "?"}) · ${attempt.result ?? "?"} · ${String(attempt.seconds ?? 0)} s · ${NUMBER.format(attempt.tokens_in ?? 0)} jetons envoyés, ${NUMBER.format(attempt.tokens_out ?? 0)} reçus`,
    );
  }
  if (details.lone_sections?.length) {
    lines.push(`Sections à une seule source : ${details.lone_sections.join(" ; ")}`);
  }
  if (details.repeated_paragraphs?.length) {
    lines.push(`Paragraphes répétés : ${details.repeated_paragraphs.join(" ; ")}`);
  }
  if (details.matter_words !== undefined) {
    lines.push(
      `Matière : ${NUMBER.format(details.matter_words)} mots de sources${details.thin_matter ? " (trop peu)" : ""} ; longueur demandée ${brief.length ?? "?"}, utilisée ${brief.length_used ?? "?"}`,
    );
  }
  if (details.unsupported !== undefined) {
    lines.push(
      `Absents des sources : ${details.unsupported.length === 0 ? "aucun" : details.unsupported.map((f) => f.text).join(" ; ")}`,
    );
  }
  if (details.copying !== undefined) {
    lines.push(
      `Recopie : ${String(Math.round((details.copying.share ?? 0) * 100))} % des suites de 8 mots, ${String(details.copying.passages?.length ?? 0)} passage(s) de 12 mots ou plus`,
    );
  }
  if (details.context_overflow) {
    lines.push("La fenêtre de contexte a été dépassée.");
  }
  return lines.join("\n");
}

/** « Détails de génération »: folded by default, with a copy button. */
export function GenerationDetails({ details, heading }: { details: Record<string, unknown>; heading: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  if (Object.keys(details).length === 0) {
    return <p className={styles.meta}>{t("draft.details.none")}</p>;
  }
  const text = detailsText(details, heading);
  return (
    <details>
      <summary>{t("draft.details.title")}</summary>
      <pre className={styles.journal} style={{ whiteSpace: "pre-wrap" }}>
        {text}
      </pre>
      <p className={styles.row}>
        <button
          type="button"
          className={styles.button}
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => {
              setCopied(true);
            });
          }}
        >
          {t("draft.details.copy")}
        </button>
        {copied && <span className={styles.meta}>{t("draft.details.copied")}</span>}
      </p>
    </details>
  );
}
