// SPDX-License-Identifier: AGPL-3.0-or-later
// Words for the codes the API returns: legal statuses, reasons, errors (U01, ADR-0031).
import type { TFunction } from "i18next";
import { ApiError } from "../../api/client.ts";

const LEGAL = ["full_text", "summary_only", "refused", "unknown"] as const;
const TEXT = ["pending", "full_text", "summary_only", "manual"] as const;
const REASONS = [
  "robots_allowed",
  "robots_missing",
  "robots_disallowed",
  "robots_unreachable",
  "tdm_reserved_file",
  "tdm_reserved_header",
  "tdm_reserved_meta",
  "tdm_not_reserved",
  "tdm_not_reserved_file",
  "tdm_not_reserved_header",
  "tdm_not_reserved_meta",
  "feed_only",
  "declared_by_user",
  "no_text_found",
  "not_html",
  "not_a_feed",
  "fetch_timeout",
  "fetch_network_error",
  "fetch_address_not_allowed",
  "fetch_too_large",
  "fetch_too_many_redirects",
  "fetch_scheme_not_allowed",
  "fetch_port_not_allowed",
  "fetch_invalid_url",
] as const;
const ERRORS = [
  "invalid_url",
  "fetch_http_error",
  "fetch_refused",
  "feed_not_found",
  "already_followed",
  "invalid_name",
  "invalid_interval",
  "invalid_title",
  "invalid_text",
  "invalid_declaration",
  "no_keywords",
  "no_sources",
  "invalid_terms",
  "invalid_languages",
  "invalid_description",
  "name_taken",
  "unknown_source",
  "invalid_query",
  "too_many_terms",
  "term_too_long",
  "version_changed",
  "version_not_found",
  "invalid_document",
  "too_large",
  "not_an_image",
] as const;

export const INTERVALS = ["15", "30", "60", "180", "360", "720", "1440", "10080"] as const;

function among<T extends string>(list: readonly T[], value: string): value is T {
  return (list as readonly string[]).includes(value);
}

export type Tone = "good" | "limited" | "blocked" | "neutral";

export function legalLabel(t: TFunction, status: string): string {
  return among(LEGAL, status) ? t(`legal.${status}`) : status;
}

export function legalTone(status: string): Tone {
  return status === "full_text"
    ? "good"
    : status === "summary_only"
      ? "limited"
      : status === "refused"
        ? "blocked"
        : "neutral";
}

export function textLabel(t: TFunction, status: string): string {
  return among(TEXT, status) ? t(`text.${status}`) : status;
}

export function textTone(status: string): Tone {
  return status === "full_text" ? "good" : status === "summary_only" ? "limited" : "neutral";
}

export function reasonText(t: TFunction, code: string | null): string {
  if (code === null || code === "") {
    return "";
  }
  const http = /^(?:fetch_)?http_(\d+)$/.exec(code);
  if (http?.[1] !== undefined) {
    return t("reasons.http", { status: http[1] });
  }
  return among(REASONS, code) ? t(`reasons.${code}`) : t("reasons.unknown", { code });
}

/** The message for a failed request: the code of the API when the interface knows it. */
export function errorText(t: TFunction, error: Error): string {
  if (error instanceof ApiError && error.detail !== null) {
    if (among(ERRORS, error.detail)) {
      return t(`errors.${error.detail}`);
    }
    if (among(REASONS, error.detail)) {
      return t(`reasons.${error.detail}`);
    }
  }
  // A 422 the interface cannot name: a value of the form, not a passing failure.
  if (error instanceof ApiError && error.status === 422) {
    return t("errors.invalid_input");
  }
  return t("errors.generic");
}

const DATE = new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(value: string): string {
  return DATE.format(new Date(value));
}

/** Links come from feeds and pages: only web addresses become links. */
export function isWebUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

export const TOPIC_LANGUAGES = ["fr", "en", "de", "nl", "es", "it", "pt"] as const;

export function languageName(t: TFunction, code: string): string {
  return among(TOPIC_LANGUAGES, code) ? t(`topics.languageNames.${code}`) : code;
}

/** "« IA » dans le titre (+3) · récent (+2)": the score, read aloud (F-VEI-02). */
export function explain(
  t: TFunction,
  contributions: readonly { term: string; where: string; count: number; points: number }[],
  freshness = 0,
): string {
  const parts = contributions.map((c) =>
    c.where === "source"
      ? t("topics.fromSource", { points: c.points })
      : c.where === "title"
        ? t("topics.inTitle", { term: c.term, points: c.points })
        : t("topics.inText", { term: c.term, count: c.count, points: c.points }),
  );
  if (freshness > 0) {
    parts.push(t("topics.fresh", { points: freshness }));
  }
  return parts.join(" · ");
}

function fold(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Whether `text` contains `query`, ignoring case and accents (« mo » finds « Moto »). */
export function matchesFilter(text: string, query: string): boolean {
  return fold(text).includes(fold(query.trim()));
}
