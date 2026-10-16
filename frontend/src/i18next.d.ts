// SPDX-License-Identifier: AGPL-3.0-or-later
// Typed translation keys: a missing or misspelt key is a type error.
import "i18next";
import type { defaultNS, resources } from "./i18n.ts";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS;
    resources: (typeof resources)["fr"];
  }
}
