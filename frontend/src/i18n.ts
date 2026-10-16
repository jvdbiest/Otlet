// SPDX-License-Identifier: AGPL-3.0-or-later
// Interface strings live in src/locales, one catalogue per language, as ICU messages
// (TECH_CHOICES §6.5). French is the reference; English comes later in É1.
import i18next from "i18next";
import ICU from "i18next-icu";
import { initReactI18next } from "react-i18next";
import fr from "./locales/fr.json";

export const defaultNS = "translation";
export const resources = { fr: { translation: fr } } as const;

void i18next
  .use(ICU)
  .use(initReactI18next)
  .init({
    lng: "fr",
    fallbackLng: "fr",
    resources,
    defaultNS,
    interpolation: { escapeValue: false }, // React escapes already
    returnNull: false,
  });

export default i18next;
