import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { getDebugState } from "@shared/lib/debug-bar";
import { toast } from "@shared/lib/toast";

import en from "./locales/en.json";
import ru from "./locales/ru.json";

export const SUPPORTED_LANGUAGES = ["en", "ru"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "remnashop_language";

function isSupportedLanguage(value: string | null): value is SupportedLanguage {
  return SUPPORTED_LANGUAGES.includes(value as SupportedLanguage);
}

function detectInitialLanguage(): SupportedLanguage {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isSupportedLanguage(stored)) return stored;

  const browserLanguage = navigator.language.slice(0, 2);
  return isSupportedLanguage(browserLanguage) ? browserLanguage : "en";
}

const reportedKeys = new Set<string>();

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
  },
  lng: detectInitialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  saveMissing: true,
  missingKeyHandler: (_languages, _namespace, key) => {
    if (!getDebugState().missingKeys || reportedKeys.has(key)) return;
    reportedKeys.add(key);
    // Deferred: a handler firing mid-render can't synchronously push a toast.
    setTimeout(() => toast.warning(`i18n: ${key}`), 0);
  },
});

i18n.on("languageChanged", (language) => {
  localStorage.setItem(STORAGE_KEY, language);
});

export default i18n;
