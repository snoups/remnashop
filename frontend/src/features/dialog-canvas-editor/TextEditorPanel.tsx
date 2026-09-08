import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { splitTextKey, updateDialogText } from "@entities/dialogs/api";
import { getErrorMessage } from "@shared/api/http";
import { resetTranslation } from "@entities/translations/api";
import type { TranslationEntry } from "@entities/translations/api";
import { toast } from "@shared/lib/toast";

interface TextEditorPanelProps {
  textKey: string;
  entries: TranslationEntry[];
  locales: string[];
  activeLocale: string;
  onActiveLocaleChange: (locale: string) => void;
  variableKeys: string[];
  canUpdate: boolean;
  canReset: boolean;
  onSaved: (entry: TranslationEntry) => void;
}

export function TextEditorPanel({
  textKey,
  entries,
  locales,
  activeLocale,
  onActiveLocaleChange,
  variableKeys,
  canUpdate,
  canReset,
  onSaved,
}: TextEditorPanelProps) {
  const { t } = useTranslation();
  const { messageId, attributeId } = splitTextKey(textKey);
  const entry = entries.find(
    (e) => e.locale === activeLocale && e.message_id === messageId && e.attribute_id === attributeId,
  );
  const [draft, setDraft] = useState(entry?.value ?? "");

  useEffect(() => {
    setDraft(entry?.value ?? "");
    // Re-syncs the draft whenever the selection or locale changes, or a save/reset
    // brings back a new entry.value -- but not on every keystroke (entry.value only
    // changes server-side).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textKey, activeLocale, entry?.value]);

  const handleSave = async () => {
    try {
      const updated = await updateDialogText(activeLocale, messageId, attributeId, draft);
      onSaved({
        locale: updated.locale,
        message_id: updated.message_id,
        attribute_id: attributeId,
        value: updated.value,
        default_value: updated.default_value,
      });
      toast.success(t("dialogs.inspector.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleReset = async () => {
    try {
      const reset = await resetTranslation(activeLocale, messageId, attributeId);
      onSaved(reset);
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div>
      {locales.length > 1 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {locales.map((locale) => (
            <button
              key={locale}
              type="button"
              onClick={() => onActiveLocaleChange(locale)}
              className={`rounded-full px-2.5 py-1 text-[11.5px] ${
                locale === activeLocale ? "bg-accent text-primary" : "text-foreground/70 hover:bg-white/[0.06]"
              }`}
            >
              {locale}
            </button>
          ))}
        </div>
      )}
      <input
        type="text"
        value={draft}
        disabled={!canUpdate}
        onChange={(event) => setDraft(event.target.value)}
        className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
      />
      {variableKeys.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {variableKeys.map((name) => (
            <button
              key={name}
              type="button"
              disabled={!canUpdate}
              onClick={() => setDraft((current) => `${current}{ $${name} }`)}
              className="rounded-full border border-white/[0.12] px-2 py-0.5 text-[11px] text-foreground/70 hover:bg-white/[0.06] disabled:opacity-30"
            >
              {`{ $${name} }`}
            </button>
          ))}
        </div>
      )}
      <div className="mt-2 flex gap-2">
        {canUpdate && (
          <button
            type="button"
            disabled={draft === (entry?.value ?? "")}
            onClick={() => void handleSave()}
            className="rounded-full border border-white/[0.12] px-3 py-1.5 text-[12px] text-foreground/80 hover:bg-white/[0.06] disabled:opacity-30"
          >
            {t("dialogs.inspector.textSave")}
          </button>
        )}
        {canReset && entry && entry.value !== entry.default_value && (
          <button
            type="button"
            onClick={() => void handleReset()}
            className="rounded-full border border-white/[0.12] px-3 py-1.5 text-[12px] text-foreground/60 hover:bg-white/[0.06]"
          >
            {t("dialogs.inspector.textReset")}
          </button>
        )}
      </div>
    </div>
  );
}
