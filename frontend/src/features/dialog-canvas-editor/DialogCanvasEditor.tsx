import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchBannerImageBlob } from "@entities/banners/api";
import {
  createCustomWindow,
  deleteCustomWindow,
  getCatalog,
  listWindows,
  replaceButtons,
  toButtonInput,
  windowTextKeys,
  type DialogButtonItem,
  type DialogCatalog,
  type DialogWindow,
} from "@entities/dialogs/api";
import { listActiveLocales, listTranslations, type TranslationEntry } from "@entities/translations/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useCurrentUser } from "@entities/user/use-current-user";
import { ButtonInspector } from "@features/dialog-canvas-editor/ButtonInspector";
import { ConditionSimulator } from "@features/dialog-canvas-editor/ConditionSimulator";
import { DialogCanvas } from "@features/dialog-canvas-editor/DialogCanvas";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { WindowInspector } from "@features/dialog-canvas-editor/WindowInspector";
import { WindowSwitcher } from "@features/dialog-canvas-editor/WindowSwitcher";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

export type Selection = { kind: "window" } | { kind: "text" } | { kind: "button"; textKey: string };

function randomId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(16).slice(2).padEnd(32, "0");
}

function useSelectedWindow(windows: DialogWindow[], selectedKey: string | null): DialogWindow | null {
  if (selectedKey === null) return null;
  return windows.find((window) => window.key === selectedKey) ?? null;
}

export function DialogCanvasEditor() {
  const { t } = useTranslation();
  const currentUserState = useCurrentUser();
  const permissions = currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const [windowsState, reloadWindows, setWindowsData] = useAsyncResource(listWindows);
  const [localesState] = useAsyncResource(listActiveLocales);
  const [entriesState, reloadEntries, setEntriesData] = useAsyncResource(listTranslations);
  const [catalogState] = useAsyncResource(getCatalog);
  const catalog: DialogCatalog | null = catalogState.kind === "ready" ? catalogState.data : null;
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>({ kind: "window" });
  const [previewLocale, setPreviewLocale] = useState<string | null>(null);
  const [bannerUrl, setBannerUrl] = useState<string | null>(null);
  const [pendingButtons, setPendingButtons] = useState<DialogButtonItem[] | null>(null);
  const [conditionToggles, setConditionToggles] = useState<Record<string, boolean>>({});
  const [pendingWindowSwitch, setPendingWindowSwitch] = useState<string | null>(null);

  const windows = windowsState.kind === "ready" ? windowsState.data : [];
  const activeLocales = localesState.kind === "ready" ? localesState.data.active : [];
  const entries = entriesState.kind === "ready" ? entriesState.data : [];
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
    setSelection({ kind: "window" });
    setPendingButtons(null);
    setConditionToggles({});
  }, [selectedKey]);

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

  const textByKey: Record<string, string> = {};
  if (selectedWindow && previewLocale) {
    const keys = new Set(windowTextKeys(selectedWindow));
    for (const entry of entries) {
      if (entry.locale !== previewLocale) continue;
      const fullKey = entry.attribute_id ? `${entry.message_id}.${entry.attribute_id}` : entry.message_id;
      if (keys.has(fullKey)) textByKey[fullKey] = entry.value;
    }
  }

  const handleEntrySaved = (updated: TranslationEntry) => {
    if (entriesState.kind !== "ready") return;
    const next = entriesState.data.filter(
      (e) => !(e.locale === updated.locale && e.message_id === updated.message_id && e.attribute_id === updated.attribute_id),
    );
    next.push(updated);
    setEntriesData(next);
  };

  const buttons = pendingButtons ?? selectedWindow?.buttons ?? [];
  const isDirty = pendingButtons !== null;
  const canEditButtons = permissions.includes("DIALOGS_WINDOWS_BUTTONS_UPDATE");
  const referencedConditions = [
    ...new Set(buttons.map((b) => b.visibility_condition).filter((c): c is string => c !== null)),
  ];

  const handleButtonChange = (updated: DialogButtonItem) => {
    setPendingButtons(buttons.map((b) => (b.row === updated.row && b.column === updated.column ? updated : b)));
  };

  const handleButtonDelete = () => {
    if (selection.kind !== "button") return;
    setPendingButtons(buttons.filter((b) => b.text_key !== selection.textKey));
    setSelection({ kind: "window" });
  };

  const handleSaveButtons = async () => {
    if (!selectedWindow) return;
    try {
      const updated = await replaceButtons(selectedWindow.key, buttons.map(toButtonInput));
      setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)));
      setPendingButtons(null);
      reloadEntries();
      toast.success(t("dialogs.inspector.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleDiscardButtons = () => setPendingButtons(null);

  const canCreateWindow = permissions.includes("DIALOGS_WINDOWS_CREATE");
  const canDeleteWindow = permissions.includes("DIALOGS_WINDOWS_DELETE");

  const handleCreateWindow = async (titleText: string, bannerName: string | null) => {
    try {
      const created = await createCustomWindow(titleText, bannerName);
      setWindowsData([...windows, created]);
      setSelectedKey(created.key);
      toast.success(t("dialogs.inspector.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleDeleteWindow = async (key: string) => {
    try {
      await deleteCustomWindow(key);
      setWindowsData(windows.filter((w) => w.key !== key));
      if (selectedKey === key) setSelectedKey(null);
      toast.success(t("dialogs.windowList.deleted"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleAddButton = () => {
    if (!catalog || catalog.navigable_window_keys.length === 0) return;
    const rows = buttons.map((b) => b.row);
    const nextRow = rows.length > 0 ? Math.max(...rows) + 1 : 0;
    const newButton: DialogButtonItem = {
      row: nextRow,
      column: 0,
      text_key: `msg-dialog-custom-${randomId()}`,
      icon_custom_emoji_id: null,
      style: null,
      visibility_condition: null,
      link_type: "navigate",
      action_key: null,
      target_window_key: catalog.navigable_window_keys[0],
      url_value: null,
      is_hidden: false,
    };
    setPendingButtons([...buttons, newButton]);
    setSelection({ kind: "button", textKey: newButton.text_key });
  };

  const handleSelectWindow = (key: string) => {
    if (isDirty) {
      setPendingWindowSwitch(key);
      return;
    }
    setSelectedKey(key);
  };

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <WindowSwitcher
        windows={windows}
        selectedKey={selectedKey}
        onSelect={handleSelectWindow}
        canCreate={canCreateWindow}
        canDelete={canDeleteWindow}
        onCreate={(title, banner) => void handleCreateWindow(title, banner)}
        onDelete={(key) => void handleDeleteWindow(key)}
      />
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
          <DialogCanvas
            window={selectedWindow}
            buttons={buttons}
            textByKey={textByKey}
            bannerUrl={bannerUrl}
            selection={selection}
            onSelect={setSelection}
            conditionToggles={conditionToggles}
            canEditButtons={canEditButtons}
            onReorderButtons={setPendingButtons}
          />
        ) : null}
        {canEditButtons && catalog && (
          <button
            type="button"
            onClick={handleAddButton}
            className="mt-2 w-full rounded-lg border border-dashed border-white/[0.12] py-1.5 text-[12px] text-foreground/70 hover:bg-white/[0.06]"
          >
            {t("dialogs.inspector.buttonAdd")}
          </button>
        )}
        {isDirty && canEditButtons && (
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => void handleSaveButtons()}
              className="rounded-full bg-accent px-3 py-1.5 text-[12.5px] text-primary hover:bg-primary/20"
            >
              {t("dialogs.inspector.buttonsSave")}
            </button>
            <button
              type="button"
              onClick={handleDiscardButtons}
              className="rounded-full border border-white/[0.12] px-3 py-1.5 text-[12.5px] text-foreground/70 hover:bg-white/[0.06]"
            >
              {t("dialogs.inspector.buttonsDiscard")}
            </button>
          </div>
        )}
        <ConditionSimulator
          conditions={referencedConditions}
          toggles={conditionToggles}
          onToggle={(condition, value) => setConditionToggles((current) => ({ ...current, [condition]: value }))}
        />
      </div>
      {selectedWindow && selection.kind === "window" ? (
        <WindowInspector
          window={selectedWindow}
          onWindowUpdated={(updated) => {
            setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)));
          }}
          onResetAll={reloadWindows}
        />
      ) : null}
      {selectedWindow && selection.kind === "text" && previewLocale && entriesState.kind === "ready" ? (
        <div className="w-full shrink-0 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 lg:w-64">
          <h3 className="mb-3 text-[13px] font-semibold text-foreground">{t("dialogs.inspector.textTitle")}</h3>
          <TextEditorPanel
            textKey={selectedWindow.text_keys[0] ?? ""}
            entries={entries}
            locales={activeLocales}
            activeLocale={previewLocale}
            onActiveLocaleChange={setPreviewLocale}
            variableKeys={catalog?.text_variable_keys ?? []}
            canUpdate={permissions.includes("DIALOGS_TEXT_UPDATE")}
            canReset={permissions.includes("TRANSLATIONS_RESET")}
            onSaved={handleEntrySaved}
          />
        </div>
      ) : null}
      {selectedWindow && selection.kind === "button" && catalog && previewLocale && entriesState.kind === "ready" ? (
        (() => {
          const button = buttons.find((b) => b.text_key === selection.textKey);
          if (!button) return null;
          return (
            <ButtonInspector
              button={button}
              windowKind={selectedWindow.kind}
              catalog={catalog}
              entries={entries}
              locales={activeLocales}
              activeLocale={previewLocale}
              onActiveLocaleChange={setPreviewLocale}
              canEditText={permissions.includes("DIALOGS_TEXT_UPDATE")}
              canResetText={permissions.includes("TRANSLATIONS_RESET")}
              canEditButtons={canEditButtons}
              onEntrySaved={handleEntrySaved}
              onChange={handleButtonChange}
              onDelete={handleButtonDelete}
            />
          );
        })()
      ) : null}
      {pendingWindowSwitch && (
        <ConfirmDialog
          title={t("dialogs.inspector.buttonsDiscard")}
          message={t("dialogs.inspector.discardSwitchConfirm")}
          confirmLabel={t("dialogs.inspector.discardSwitchConfirmButton")}
          cancelLabel={t("dialogs.inspector.resetWindowCancelButton")}
          danger
          onConfirm={() => {
            setSelectedKey(pendingWindowSwitch);
            setPendingWindowSwitch(null);
          }}
          onCancel={() => setPendingWindowSwitch(null)}
        />
      )}
    </div>
  );
}
