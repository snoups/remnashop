import { Languages, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { localeLabel } from "@shared/i18n/locale-label";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

import { addLocale, removeLocale } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";

interface LocaleTabsProps {
  title: string;
  form: EditorForm;
  onChange: (form: EditorForm) => void;
  activeLocale: string;
  onLocaleChange: (locale: string) => void;
  /** the bot's active locales, the ones a text can be added for */
  botLocales: string[];
  disabled: boolean;
  /** false: only switches the locale, adding/removing is left to another card */
  manageLocales?: boolean;
}

// the broadcast's languages are the Telegram content's keys, shared by the email editor
export function LocaleTabs({
  title,
  form,
  onChange,
  activeLocale,
  onLocaleChange,
  botLocales,
  disabled,
  manageLocales = true,
}: LocaleTabsProps) {
  const { t, i18n } = useTranslation();
  const locales = Object.keys(form.contents);
  const missing = botLocales.filter((locale) => !locales.includes(locale));

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`${EYEBROW_CLASS} mr-1.5`}>{title}</span>
      <div className="w-fit max-w-full">
        <PillTabs
          items={locales.map((locale) => ({
            key: locale,
            label: (
              <span className="flex items-center gap-1.5">
                {locale.toUpperCase()}
                {locale === form.default_locale && (
                  <span className="text-[10px] opacity-80">{t("broadcasts.editor.defaultLocale")}</span>
                )}
              </span>
            ),
          }))}
          activeKey={activeLocale}
          onSelect={onLocaleChange}
        />
      </div>
      {manageLocales && activeLocale !== form.default_locale && (
        <IconButton
          size="8"
          tone="danger"
          disabled={disabled}
          onClick={() => {
            onChange(removeLocale(form, activeLocale));
            onLocaleChange(form.default_locale);
          }}
        >
          <Trash2 className="size-4" />
        </IconButton>
      )}
      {manageLocales && missing.length > 0 && (
        <div className="w-44">
          <SelectDropdown
            value=""
            size="compact"
            icon={Languages}
            disabled={disabled}
            placeholder={t("broadcasts.editor.addLocale")}
            options={missing.map((locale) => ({ value: locale, label: localeLabel(locale, i18n.language) }))}
            onChange={(locale) => {
              onChange(addLocale(form, locale));
              onLocaleChange(locale);
            }}
          />
        </div>
      )}
      <span className="ml-auto text-[12px] text-muted-foreground">
        {t("broadcasts.editor.fallbackHint", { locale: form.default_locale.toUpperCase() })}
      </span>
    </div>
  );
}
