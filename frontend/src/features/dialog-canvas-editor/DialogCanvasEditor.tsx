import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchBannerImageBlob } from "@entities/banners/api";
import { listWindows, windowTextKeys, type DialogWindow } from "@entities/dialogs/api";
import { listActiveLocales, listTranslations } from "@entities/translations/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogCanvas } from "@features/dialog-canvas-editor/DialogCanvas";
import { WindowInspector } from "@features/dialog-canvas-editor/WindowInspector";
import { WindowSwitcher } from "@features/dialog-canvas-editor/WindowSwitcher";

function useSelectedWindow(windows: DialogWindow[], selectedKey: string | null): DialogWindow | null {
  if (selectedKey === null) return null;
  return windows.find((window) => window.key === selectedKey) ?? null;
}

export function DialogCanvasEditor() {
  const { t } = useTranslation();
  const [windowsState, reloadWindows, setWindowsData] = useAsyncResource(listWindows);
  const [localesState] = useAsyncResource(listActiveLocales);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [previewLocale, setPreviewLocale] = useState<string | null>(null);
  const [textByKey, setTextByKey] = useState<Record<string, string>>({});
  const [bannerUrl, setBannerUrl] = useState<string | null>(null);

  const windows = windowsState.kind === "ready" ? windowsState.data : [];
  const activeLocales = localesState.kind === "ready" ? localesState.data.active : [];
  const selectedWindow = useSelectedWindow(windows, selectedKey);

  useEffect(() => {
    if (windowsState.kind === "ready" && selectedKey === null && windowsState.data.length > 0) {
      setSelectedKey(windowsState.data[0].key);
    }
  }, [windowsState, selectedKey]);

  useEffect(() => {
    if (localesState.kind === "ready" && previewLocale === null && localesState.data.active.length > 0) {
      setPreviewLocale(localesState.data.active[0]);
    }
  }, [localesState, previewLocale]);

  useEffect(() => {
    if (!selectedWindow || !previewLocale) return;
    const controller = new AbortController();
    const keys = new Set(windowTextKeys(selectedWindow));
    listTranslations(controller.signal)
      .then((entries) => {
        if (controller.signal.aborted) return;
        const next: Record<string, string> = {};
        for (const entry of entries) {
          if (entry.locale !== previewLocale) continue;
          const fullKey = entry.attribute_id ? `${entry.message_id}.${entry.attribute_id}` : entry.message_id;
          if (keys.has(fullKey)) next[fullKey] = entry.value;
        }
        setTextByKey(next);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [selectedWindow, previewLocale]);

  useEffect(() => {
    if (!selectedWindow?.banner_name || !previewLocale) {
      setBannerUrl(null);
      return;
    }
    const controller = new AbortController();
    let objectUrl: string | null = null;
    fetchBannerImageBlob(selectedWindow.banner_name, previewLocale, controller.signal)
      .then((blob) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setBannerUrl(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setBannerUrl(null);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedWindow, previewLocale]);

  if (windowsState.kind === "loading") {
    return <p className="p-4 text-[13.5px] text-muted-foreground">{t("dialogs.loading")}</p>;
  }
  if (windowsState.kind === "error") {
    return <p className="p-4 text-[13.5px] text-error">{t("dialogs.loadError")}</p>;
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <WindowSwitcher windows={windows} selectedKey={selectedKey} onSelect={setSelectedKey} />
      <div className="flex-1 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {activeLocales.length > 1 && (
          <select
            className="mb-3 rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[12.5px] text-foreground"
            value={previewLocale ?? ""}
            onChange={(event) => setPreviewLocale(event.target.value)}
          >
            {activeLocales.map((locale) => (
              <option key={locale} value={locale}>
                {locale}
              </option>
            ))}
          </select>
        )}
        {selectedWindow ? (
          <DialogCanvas window={selectedWindow} textByKey={textByKey} bannerUrl={bannerUrl} />
        ) : null}
      </div>
      {selectedWindow ? (
        <WindowInspector
          window={selectedWindow}
          onWindowUpdated={(updated) => {
            setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)));
          }}
          onResetAll={reloadWindows}
        />
      ) : null}
    </div>
  );
}
