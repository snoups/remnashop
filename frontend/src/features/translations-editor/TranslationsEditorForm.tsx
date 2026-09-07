import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { LocalesManager } from "@features/translations-editor/LocalesManager";
import { getErrorMessage } from "@shared/api/http";
import {
  listActiveLocales,
  listTranslations,
  resetTranslation,
  type TranslationEntry,
  updateTranslation,
} from "@entities/translations/api";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";

interface Row {
  messageId: string;
  attributeId: string;
  byLocale: Record<string, TranslationEntry>;
}

function toRows(entries: TranslationEntry[]): Row[] {
  const rows = new Map<string, Row>();
  for (const entry of entries) {
    const key = `${entry.message_id}.${entry.attribute_id}`;
    const row = rows.get(key) ?? { messageId: entry.message_id, attributeId: entry.attribute_id, byLocale: {} };
    row.byLocale[entry.locale] = entry;
    rows.set(key, row);
  }
  return [...rows.values()].sort((a, b) => a.messageId.localeCompare(b.messageId));
}

export function TranslationsEditorForm() {
  const { t } = useTranslation();
  const [localesState, , setLocalesState] = useAsyncResource(listActiveLocales);
  const [rowsState, reloadRows, setRowsState] = useAsyncResource(listTranslations);

  const handleSave = async (row: Row, locale: string, value: string) => {
    try {
      const updated = await updateTranslation(locale, row.messageId, row.attributeId, value);
      if (rowsState.kind !== "ready") return;
      setRowsState(
        rowsState.data.map((entry) =>
          entry.locale === locale && entry.message_id === row.messageId && entry.attribute_id === row.attributeId
            ? updated
            : entry,
        ),
      );
      toast.success(t("settings.translationsEditor.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleReset = async (row: Row, locale: string) => {
    try {
      const reset = await resetTranslation(locale, row.messageId, row.attributeId);
      if (rowsState.kind !== "ready") return;
      setRowsState(
        rowsState.data.map((entry) =>
          entry.locale === locale && entry.message_id === row.messageId && entry.attribute_id === row.attributeId
            ? reset
            : entry,
        ),
      );
      toast.success(t("settings.translationsEditor.reset"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Languages className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.translationsEditor.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("settings.translationsEditor.description")}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {localesState.kind === "ready" && (
          <LocalesManager
            locales={localesState.data}
            onChange={(locales) => {
              setLocalesState(locales);
              reloadRows();
            }}
          />
        )}

        {rowsState.kind === "loading" && (
          <Spinner />
        )}
        {rowsState.kind === "error" && (
          <p className="text-sm text-error">{t("settings.translationsEditor.loadError")}</p>
        )}
        {rowsState.kind === "ready" && localesState.kind === "ready" && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="p-2">{"key"}</th>
                  {localesState.data.active.map((locale) => (
                    <th key={locale} className="p-2">
                      {locale}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {toRows(rowsState.data).map((row) => (
                  <tr key={`${row.messageId}.${row.attributeId}`} className="border-t border-border">
                    <td className="p-2 font-mono text-xs text-foreground/80">
                      {row.attributeId ? `${row.messageId}.${row.attributeId}` : row.messageId}
                    </td>
                    {localesState.data.active.map((locale) => {
                      const entry = row.byLocale[locale];
                      return (
                        <td key={locale} className="p-2">
                          <div className="flex items-center gap-1">
                            <input
                              key={entry?.value ?? ""}
                              defaultValue={entry?.value ?? ""}
                              onBlur={(event) => {
                                if (event.target.value === (entry?.value ?? "")) return;
                                void handleSave(row, locale, event.target.value);
                              }}
                              className="w-48 rounded-lg border border-border bg-input/60 px-2 py-1 text-xs"
                            />
                            <button
                              type="button"
                              disabled={entry?.value === entry?.default_value}
                              onClick={() => void handleReset(row, locale)}
                              className="text-[11px] text-foreground/60 hover:text-foreground disabled:opacity-30"
                            >
                              {t("settings.translationsEditor.resetToDefault")}
                            </button>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
