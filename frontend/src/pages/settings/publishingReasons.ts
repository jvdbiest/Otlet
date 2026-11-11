// SPDX-License-Identifier: AGPL-3.0-or-later
// The sentences of the codes that publishing gives (U07): refusals of the API, results of
// « Tester », failures of a send.
import type { TFunction } from "i18next";
import { ApiError } from "../../api/client.ts";
import { errorText } from "../watch/labels.ts";

const REASONS = [
  "address_not_allowed",
  "already_published",
  "bad_credentials",
  "forbidden",
  "invalid_name",
  "invalid_password",
  "invalid_tag",
  "invalid_url",
  "invalid_username",
  "name_taken",
  "no_rest_api",
  "not_logged_in",
  "not_validated",
  "not_wordpress",
  "redirected",
  "refused",
  "remote_deleted",
  "secrets_unavailable",
  "send_running",
  "server_error",
  "several_posts",
  "site_not_found",
  "tag_not_allowed",
  "timeout",
  "too_close",
  "too_close_blocked",
  "too_close_pending",
  "too_many_terms",
  "unreachable",
  "version_changed",
] as const;
type Reason = (typeof REASONS)[number];

function isReason(code: string): code is Reason {
  return (REASONS as readonly string[]).includes(code);
}

/** The sentence of a code; an unknown code is shown as it is. */
export function reasonText(t: TFunction, code: string | null | undefined): string {
  if (code === null || code === undefined) {
    return "";
  }
  return isReason(code) ? t(`publishing.reasons.${code}`) : code;
}

export function publishingError(t: TFunction, error: Error | null): string | null {
  if (error === null) {
    return null;
  }
  if (error instanceof ApiError && error.detail !== null && isReason(error.detail)) {
    return reasonText(t, error.detail);
  }
  return errorText(t, error);
}
