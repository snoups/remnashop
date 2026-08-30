import { useState } from "react";
import { useTranslation } from "react-i18next";

import { addLocale, type ActiveLocalesResult, removeLocale } from "@entities/translations/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";

interface LocalesManagerProps {
  locales: ActiveLocalesResult;
  onChange: (locales: ActiveLocalesResult) => void;
}

export function LocalesManager({ locales, onChange }: LocalesManagerProps) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState("");
  // `selected` only holds an explicit pick; the first available locale is the
  // implicit one, so adding never submits a code that just left the list.
  const value = locales.available.includes(selected) ? selected : (locales.available[0] ?? "");

  const handleAdd = async () => {
    if (!value) return;
    try {
      setSelected("");
      onChange(await addLocale(value));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleRemove = async (locale: string) => {
    try {
      onChange(await removeLocale(locale));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {locales.active.map((locale) => (
        <span
          key={locale}
          className="flex items-center gap-1 rounded-full border border-border bg-input/60 px-3 py-1 text-xs font-medium uppercase"
        >
          {locale}
          {locale !== "en" && (
            <button
              type="button"
              onClick={() => void handleRemove(locale)}
              aria-label={t("settings.translationsEditor.removeLocale")}
              className="text-foreground/60 hover:text-foreground"
            >
              ×
            </button>
          )}
        </span>
      ))}
      {locales.available.length > 0 && (
        <div className="flex items-center gap-2">
          <select
            value={value}
            onChange={(event) => setSelected(event.target.value)}
            className="rounded-full border border-border bg-input/60 px-2 py-1 text-xs uppercase"
          >
            {locales.available.map((locale) => (
              <option key={locale} value={locale}>
                {locale}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void handleAdd()}
            className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-primary hover:bg-primary/20"
          >
            {t("settings.translationsEditor.addLocale")}
          </button>
        </div>
      )}
    </div>
  );
}
