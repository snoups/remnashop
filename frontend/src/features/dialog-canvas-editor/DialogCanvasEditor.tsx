import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, MessageSquare, RotateCcw, Upload, type LucideIcon } from "lucide-react";

import { fetchBannerImageBlob } from "@entities/banners/api";
import {
  buttonKey,
  createCustomWindow,
  deleteCustomWindow,
  exportDialogs,
  getCatalog,
  importDialogs,
  invalidUrlButton,
  listWindows,
  replaceButtons,
  resetAll,
  toButtonInput,
  windowTextKeys,
  type DialogButtonItem,
  type DialogCatalog,
  type DialogExportPayload,
  type DialogWindow,
} from "@entities/dialogs/api";
import { listActiveLocales, listTranslations, type TranslationEntry } from "@entities/translations/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useCurrentUser } from "@entities/user/use-current-user";
import { ButtonInspector } from "@features/dialog-canvas-editor/ButtonInspector";
import { DialogCanvas } from "@features/dialog-canvas-editor/DialogCanvas";
import { PillTabs } from "@features/dialog-canvas-editor/PillTabs";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { WindowInspector } from "@features/dialog-canvas-editor/WindowInspector";
import { WindowSwitcher } from "@features/dialog-canvas-editor/WindowSwitcher";
import { getErrorMessage } from "@shared/api/http";
import { localeLabel } from "@shared/i18n/locale-label";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

export type Selection = { kind: "text" } | { kind: "button"; buttonKey: string };

function randomId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(16).slice(2).padEnd(32, "0");
}

function useSelectedWindow(windows: DialogWindow[], selectedKey: string | null): DialogWindow | null {
  if (selectedKey === null) return null;
  return windows.find((window) => window.key === selectedKey) ?? null;
}

function ToolbarButton({
  icon: Icon,
  label,
  danger,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  danger?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex cursor-pointer items-center gap-1.5 rounded-full border border-white/[0.12] px-3 py-1.5 text-[12.5px] transition-colors hover:bg-white/[0.06] ${
        danger ? "text-error" : "text-foreground/80"
      }`}
    >
      <Icon className="size-3.5" />
      {label}
    </button>
  );
}

export function DialogCanvasEditor() {
  const { t, i18n } = useTranslation();
  const currentUserState = useCurrentUser();
  const permissions = currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const [windowsState, reloadWindows, setWindowsData] = useAsyncResource(listWindows);
  const [localesState] = useAsyncResource(listActiveLocales);
  const [entriesState, reloadEntries, setEntriesData] = useAsyncResource(listTranslations);
  const [catalogState] = useAsyncResource(getCatalog);
  const catalog: DialogCatalog | null = catalogState.kind === "ready" ? catalogState.data : null;
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"window" | "element">("window");
  const [previewLocale, setPreviewLocale] = useState<string | null>(null);
  const [bannerUrl, setBannerUrl] = useState<string | null>(null);
  // Bumped after an upload or delete: the URL depends on bytes the effect
  // below cannot otherwise know changed.
  const [bannerNonce, setBannerNonce] = useState(0);
  const [pendingButtons, setPendingButtons] = useState<DialogButtonItem[] | null>(null);
  const [pendingWindowSwitch, setPendingWindowSwitch] = useState<string | null>(null);
  const [isResetAllConfirmOpen, setIsResetAllConfirmOpen] = useState(false);
  const [pendingImport, setPendingImport] = useState<DialogExportPayload | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    setSelection(null);
    setInspectorTab("window");
    setPendingButtons(null);
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
  }, [selectedWindow, previewLocale, bannerNonce]);

  if (windowsState.kind === "loading") {
    return <p className="p-4 text-[13.5px] text-muted-foreground">{t("dialogs.loading")}</p>;
  }
  if (windowsState.kind === "error") {
    return <p className="p-4 text-[13.5px] text-error">{t("dialogs.loadError")}</p>;
  }

  const localeText: Record<string, string> = {};
  for (const entry of entries) {
    if (entry.locale !== previewLocale) continue;
    const fullKey = entry.attribute_id ? `${entry.message_id}.${entry.attribute_id}` : entry.message_id;
    localeText[fullKey] = entry.value;
  }

  const textByKey: Record<string, string> = {};
  if (selectedWindow) {
    for (const key of windowTextKeys(selectedWindow)) {
      if (key in localeText) textByKey[key] = localeText[key];
    }
  }

  // A custom window's key is a generated uuid, so the list shows what the window
  // actually says instead.
  const windowLabels: Record<string, string> = {};
  for (const window of windows) {
    if (window.kind !== "custom") continue;
    const text = localeText[window.text_keys[0]]?.split("\n")[0].trim();
    if (text) windowLabels[window.key] = text;
  }

  const incomingLinks = new Set(
    windows.flatMap((w) => w.buttons.map((b) => b.target_window_key).filter((key) => key !== null)),
  );
  // Shown as a badge in the tree: a custom window nothing navigates to cannot
  // be reached in the bot at all.
  const unreachableKeys = new Set(
    windows
      .filter((window) => window.kind === "custom" && !incomingLinks.has(window.key))
      .map((window) => window.key),
  );

  const windowLabel = (window: DialogWindow): string =>
    window.kind === "custom"
      ? (windowLabels[window.key] ?? window.key)
      : t(`dialogs.windowList.windows.${window.key}`, { defaultValue: window.key });

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

  const handleSelect = (next: Selection) => {
    setSelection(next);
    setInspectorTab("element");
  };

  const handleButtonChange = (updated: DialogButtonItem) => {
    const key = buttonKey(updated);
    setPendingButtons(buttons.map((b) => (buttonKey(b) === key ? updated : b)));
  };

  const handleButtonDelete = () => {
    if (selection?.kind !== "button") return;
    setPendingButtons(buttons.filter((b) => buttonKey(b) !== selection.buttonKey));
    setSelection(null);
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
  const isWindowLimitReached =
    catalog !== null && windows.filter((w) => w.kind === "custom").length >= catalog.custom_window_limit;
  const brokenUrlButton = catalog ? invalidUrlButton(buttons, catalog.variable_keys) : null;
  const canDeleteWindow = permissions.includes("DIALOGS_WINDOWS_DELETE");
  const canResetAll = permissions.includes("DIALOGS_WINDOWS_RESET_ALL");

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

  const handleResetAll = async () => {
    setIsResetAllConfirmOpen(false);
    try {
      await resetAll();
      reloadWindows();
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleAddButton = () => {
    if (!catalog || catalog.navigable_window_keys.length === 0) return;
    const rows = buttons.map((b) => b.row);
    const nextRow = rows.length > 0 ? Math.max(...rows) + 1 : 0;
    const newButton: DialogButtonItem = {
      id: null,
      row: nextRow,
      column: 0,
      text_key: `msg-dialog-custom-${randomId()}`,
      style: null,
      visibility_condition: null,
      link_type: "navigate",
      action_key: null,
      target_window_key: catalog.navigable_window_keys[0],
      url_value: null,
      is_hidden: false,
    };
    setPendingButtons([...buttons, newButton]);
  };

  const handleSelectWindow = (key: string) => {
    if (isDirty) {
      setPendingWindowSwitch(key);
      return;
    }
    setSelectedKey(key);
  };

  function renderElementInspector() {
    if (!selectedWindow || selection === null) return null;
    if (previewLocale === null || entriesState.kind !== "ready") return null;
    if (selection.kind === "text") {
      return (
        <div className="w-full rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
          <h3 className="mb-3 text-[13px] font-semibold text-foreground">
            {t("dialogs.inspector.textTitle")}
          </h3>
          <TextEditorPanel
            textKey={selectedWindow.text_keys[0] ?? ""}
            entries={entries}
            locales={activeLocales}
            activeLocale={previewLocale}
            onActiveLocaleChange={setPreviewLocale}
            variableKeys={catalog?.text_variable_keys ?? []}
            multiline
            emojiInsert
            canUpdate={permissions.includes("DIALOGS_TEXT_UPDATE")}
            canReset={permissions.includes("TRANSLATIONS_RESET")}
            onSaved={handleEntrySaved}
          />
        </div>
      );
    }
    const button = buttons.find((b) => buttonKey(b) === selection.buttonKey);
    if (!button || catalog === null) return null;
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
  }

  const handleExport = async () => {
    try {
      const payload = await exportDialogs();
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `dialogs-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleFileChosen = async (file: File) => {
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (typeof parsed !== "object" || parsed === null || !("version" in parsed)) {
        throw new Error("not a dialog export");
      }
      setPendingImport(parsed as DialogExportPayload);
    } catch {
      toast.error(t("dialogs.toolbar.importInvalid"));
    }
  };

  const handleImportConfirmed = async () => {
    if (pendingImport === null) return;
    const payload = pendingImport;
    setPendingImport(null);
    try {
      await importDialogs(payload);
      reloadWindows();
      reloadEntries();
      setSelection(null);
      toast.success(t("dialogs.toolbar.imported"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const elementInspector = renderElementInspector();
  const inspectorTabs: { key: "window" | "element"; label: string }[] = [
    { key: "window", label: t("dialogs.inspector.tabWindow") },
    { key: "element", label: t("dialogs.inspector.tabElement") },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* One card: the toolbar belongs to the window it acts on, and the three
          panes are zones inside it rather than separate floating blocks. */}
      <div className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] p-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06]">
              <MessageSquare className="size-4 text-foreground" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-semibold text-foreground">
                  {selectedWindow ? windowLabel(selectedWindow) : "—"}
                </span>
                {selectedWindow?.kind === "seed" && (
                  <span className="shrink-0 rounded-full border border-border bg-white/[0.04] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("dialogs.windowList.seedBadge")}
                  </span>
                )}
              </div>
              {selectedWindow && (
                <span className="truncate font-mono text-[11.5px] text-muted-foreground">
                  {selectedWindow.key}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {permissions.includes("DIALOGS_EXPORT") && (
              <ToolbarButton icon={Download} label={t("dialogs.toolbar.export")} onClick={() => void handleExport()} />
            )}
            {permissions.includes("DIALOGS_IMPORT") && (
              <ToolbarButton
                icon={Upload}
                label={t("dialogs.toolbar.import")}
                onClick={() => fileInputRef.current?.click()}
              />
            )}
            {canResetAll && (
              <ToolbarButton
                icon={RotateCcw}
                label={t("dialogs.inspector.resetAll")}
                danger
                onClick={() => setIsResetAllConfirmOpen(true)}
              />
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                // Clear it so picking the same file twice in a row still fires.
                event.target.value = "";
                if (file) void handleFileChosen(file);
              }}
            />
          </div>
        </div>

        <div className="flex min-h-0 flex-col lg:flex-row">
          <aside className="shrink-0 border-b border-white/[0.08] p-2.5 lg:w-56 lg:border-b-0 lg:border-r">
            <WindowSwitcher
              windows={windows}
              labelOf={windowLabel}
              selectedKey={selectedKey}
              onSelect={handleSelectWindow}
              canCreate={canCreateWindow && !isWindowLimitReached}
              isLimitReached={isWindowLimitReached}
              canDelete={canDeleteWindow}
              unreachableKeys={unreachableKeys}
              dirtyKey={isDirty ? selectedKey : null}
              onCreate={(title, banner) => void handleCreateWindow(title, banner)}
              onDelete={(key) => void handleDeleteWindow(key)}
            />
          </aside>

          <div className="flex min-w-0 flex-1 flex-col items-center gap-3 p-3.5">
            {activeLocales.length > 1 && (
              <div className="w-full max-w-sm">
                <PillTabs
                  items={activeLocales.map((locale) => ({
                    key: locale,
                    label: localeLabel(locale, i18n.language),
                  }))}
                  activeKey={previewLocale}
                  onSelect={setPreviewLocale}
                />
              </div>
            )}
            {selectedWindow ? (
              <DialogCanvas
                window={selectedWindow}
                buttons={buttons}
                textByKey={textByKey}
                bannerUrl={bannerUrl}
                selection={selection}
                onSelect={handleSelect}
                canEditButtons={canEditButtons}
                onReorderButtons={setPendingButtons}
              />
            ) : null}
            {canEditButtons && catalog && (
              <button
                type="button"
                onClick={handleAddButton}
                className="w-full max-w-sm cursor-pointer rounded-xl border border-dashed border-white/[0.12] py-1.5 text-[12px] text-foreground/70 transition-colors hover:bg-white/[0.06]"
              >
                {t("dialogs.inspector.buttonAdd")}
              </button>
            )}
          </div>

          <aside className="flex shrink-0 flex-col gap-3 border-t border-white/[0.08] p-3.5 lg:w-72 lg:border-l lg:border-t-0">
            <PillTabs items={inspectorTabs} activeKey={inspectorTab} onSelect={setInspectorTab} />
            {inspectorTab === "window" ? (
              selectedWindow && (
                <WindowInspector
                  window={selectedWindow}
                  activeLocale={previewLocale}
                  bannerUrl={bannerUrl}
                  onBannerChanged={() => setBannerNonce((nonce) => nonce + 1)}
                  onWindowUpdated={(updated) => {
                    setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)));
                  }}
                />
              )
            ) : (
              (elementInspector ?? (
                <p className="rounded-xl border border-dashed border-white/[0.12] p-4 text-[12.5px] text-muted-foreground">
                  {t("dialogs.inspector.emptySelection")}
                </p>
              ))
            )}
          </aside>
        </div>

        {isDirty && canEditButtons && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-warning/25 bg-warning/[0.07] px-3.5 py-2.5">
            <div className="flex items-center gap-2">
              <span className="size-[7px] rounded-full bg-warning" />
              <span className="text-[13px] text-foreground">{t("dialogs.inspector.dirtyTitle")}</span>
              {brokenUrlButton !== null && (
                <span className="text-[12.5px] text-error">
                  {t("dialogs.inspector.buttonUrlInvalidGrid")}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDiscardButtons}
                className="cursor-pointer rounded-full border border-border px-4 py-1.5 text-[13px] text-foreground/80 transition-colors hover:bg-white/[0.06]"
              >
                {t("dialogs.inspector.buttonsDiscard")}
              </button>
              <button
                type="button"
                disabled={brokenUrlButton !== null}
                onClick={() => void handleSaveButtons()}
                className="cursor-pointer rounded-full bg-accent px-4 py-1.5 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("dialogs.inspector.buttonsSave")}
              </button>
            </div>
          </div>
        )}
      </div>

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
      {pendingImport !== null && (
        <ConfirmDialog
          title={t("dialogs.toolbar.import")}
          message={t("dialogs.toolbar.importConfirm")}
          confirmLabel={t("dialogs.toolbar.importConfirmButton")}
          cancelLabel={t("dialogs.inspector.resetWindowCancelButton")}
          danger
          onConfirm={() => void handleImportConfirmed()}
          onCancel={() => setPendingImport(null)}
        />
      )}
      {isResetAllConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetAll")}
          message={t("dialogs.inspector.resetAllConfirm")}
          confirmLabel={t("dialogs.inspector.resetAllConfirmButton")}
          cancelLabel={t("dialogs.inspector.resetWindowCancelButton")}
          danger
          onConfirm={() => void handleResetAll()}
          onCancel={() => setIsResetAllConfirmOpen(false)}
        />
      )}
    </div>
  );
}
