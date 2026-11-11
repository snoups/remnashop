import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, MessagesSquare, RotateCcw, Upload } from "lucide-react";

import { fetchBannerPreview } from "@entities/banners/api";
import {
  buttonKey,
  createCustomWindow,
  deleteCustomWindow,
  exportDialogs,
  getCatalog,
  iconIdTextKey,
  iconTextKey,
  importDialogs,
  MAX_CAPTION_LENGTH,
  MAX_TEXT_LENGTH,
  buttonLimitProblem,
  invalidUrlButton,
  listWindows,
  replaceButtons,
  resetAll,
  toButtonInput,
  variableOptions,
  windowTextKeys,
  type DialogButtonItem,
  type DialogCatalog,
  type DialogExportPayload,
  type DialogWindow,
} from "@entities/dialogs/api";
import {
  listActiveLocales,
  listTranslations,
  type TranslationEntry,
} from "@entities/translations/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePermissions } from "@entities/user/use-current-user";
import { ButtonInspector } from "@features/dialog-canvas-editor/ButtonInspector";
import { DialogCanvas } from "@features/dialog-canvas-editor/DialogCanvas";
import { InspectorDivider, InspectorHeader } from "@features/dialog-canvas-editor/InspectorParts";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { GLASS_INNER_CARD_CLASS } from "@shared/ui/classes";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { WindowInspector } from "@features/dialog-canvas-editor/WindowInspector";
import type { ShownBanner } from "@features/dialog-canvas-editor/WindowInspector";
import { WindowSwitcher } from "@features/dialog-canvas-editor/WindowSwitcher";
import { getErrorMessage } from "@shared/api/http";
import { localeLabel } from "@shared/i18n/locale-label";
import { randomId } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";
import { Tooltip } from "@shared/ui/Tooltip";
import { Button } from "@shared/ui/Button";
import { Section } from "@shared/ui/glass/Section";
import { Badge } from "@shared/ui/Badge";

export type Selection =
  { kind: "text" } | { kind: "button"; buttonKey: string };

function useSelectedWindow(
  windows: DialogWindow[],
  selectedKey: string | null,
): DialogWindow | null {
  if (selectedKey === null) return null;
  return windows.find((window) => window.key === selectedKey) ?? null;
}

export function DialogCanvasEditor() {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const [windowsState, reloadWindows, setWindowsData] =
    useAsyncResource(listWindows);
  const [localesState] = useAsyncResource(listActiveLocales);
  const [entriesState, reloadEntries, setEntriesData] =
    useAsyncResource(listTranslations);
  const [catalogState] = useAsyncResource(getCatalog);
  const catalog: DialogCatalog | null =
    catalogState.kind === "ready" ? catalogState.data : null;
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [previewLocale, setPreviewLocale] = useState<string | null>(null);
  const [banner, setBanner] = useState<ShownBanner | null>(null);
  // Bumped after an upload or delete: the URL depends on bytes the effect
  // below cannot otherwise know changed.
  const [bannerNonce, setBannerNonce] = useState(0);
  const [pendingButtons, setPendingButtons] = useState<
    DialogButtonItem[] | null
  >(null);
  const [pendingWindowSwitch, setPendingWindowSwitch] = useState<string | null>(
    null,
  );
  const [isResetAllConfirmOpen, setIsResetAllConfirmOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [pendingImport, setPendingImport] =
    useState<DialogExportPayload | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const windows = windowsState.kind === "ready" ? windowsState.data : [];
  const activeLocales =
    localesState.kind === "ready" ? localesState.data.active : [];
  const entries = entriesState.kind === "ready" ? entriesState.data : [];
  const selectedWindow = useSelectedWindow(windows, selectedKey);

  useEffect(() => {
    if (
      windowsState.kind === "ready" &&
      selectedKey === null &&
      windowsState.data.length > 0
    ) {
      setSelectedKey(windowsState.data[0].key);
    }
  }, [windowsState, selectedKey]);

  useEffect(() => {
    if (
      localesState.kind === "ready" &&
      previewLocale === null &&
      localesState.data.active.length > 0
    ) {
      setPreviewLocale(localesState.data.active[0]);
    }
  }, [localesState, previewLocale]);

  useEffect(() => {
    setSelection(null);
    setPendingButtons(null);
  }, [selectedKey]);

  useEffect(() => {
    if (!selectedWindow?.banner_name || !previewLocale) {
      setBanner(null);
      return;
    }
    const controller = new AbortController();
    let objectUrl: string | null = null;
    fetchBannerPreview(selectedWindow.banner_name, previewLocale, controller.signal)
      .then((preview) => {
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(preview.blob);
        setBanner({ url: objectUrl, name: preview.name, locale: preview.locale });
      })
      .catch(() => {
        if (!controller.signal.aborted) setBanner(null);
      });
    return () => {
      controller.abort();
      if (objectUrl) {
        // a revoked URL left in state shows a broken image until the next banner loads
        setBanner(null);
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [selectedWindow, previewLocale, bannerNonce]);

  const sectionProps = {
    icon: MessagesSquare,
    title: (
      <>
        {t("dialogs.title")}
        <Badge tone="warning" tabIndex={0} className="group relative outline-none">
          {t("dialogs.beta")}
          <Tooltip text={t("dialogs.betaHint")} side="bottom" />
        </Badge>
      </>
    ),
    description: t("dialogs.description"),
  };

  if (windowsState.kind !== "ready") {
    return (
      <Section flush {...sectionProps}>
        {windowsState.kind === "error" ? <ErrorState text={t("common.loadError")} /> : <Spinner className="p-4" />}
      </Section>
    );
  }

  const localeText: Record<string, string> = {};
  for (const entry of entries) {
    if (entry.locale !== previewLocale) continue;
    const fullKey = entry.attribute_id
      ? `${entry.message_id}.${entry.attribute_id}`
      : entry.message_id;
    localeText[fullKey] = entry.value;
  }

  const textByKey: Record<string, string> = {};
  if (selectedWindow) {
    const iconKeys = selectedWindow.buttons.flatMap((button) => [
      iconTextKey(button.text_key),
      iconIdTextKey(button.text_key),
    ]);
    for (const key of [...windowTextKeys(selectedWindow), ...iconKeys]) {
      if (key in localeText) textByKey[key] = localeText[key];
    }
  }

  const incomingLinks = new Set(
    windows.flatMap((w) =>
      w.buttons.map((b) => b.target_window_key).filter((key) => key !== null),
    ),
  );
  // Shown as a badge in the tree: a custom window nothing navigates to cannot
  // be reached in the bot at all.
  const unreachableKeys = new Set(
    windows
      .filter(
        (window) => window.kind === "custom" && !incomingLinks.has(window.key),
      )
      .map((window) => window.key),
  );

  const windowLabel = (window: DialogWindow): string =>
    window.kind === "custom"
      ? (window.name ?? window.key)
      : t(`dialogs.windowList.windows.${window.key}`, {
          defaultValue: window.key,
        });

  // An updater, not a copy of entriesState: an icon pick saves two keys back
  // to back, and the second would otherwise drop the first.
  const handleEntrySaved = (updated: TranslationEntry) =>
    setEntriesData((entries) => [
      ...entries.filter(
        (e) =>
          !(
            e.locale === updated.locale &&
            e.message_id === updated.message_id &&
            e.attribute_id === updated.attribute_id
          ),
      ),
      updated,
    ]);

  const buttons = pendingButtons ?? selectedWindow?.buttons ?? [];
  const isDirty = pendingButtons !== null;
  const canEditButtons = permissions.includes("DIALOGS_WINDOWS_BUTTONS_UPDATE");


  const handleButtonChange = (updated: DialogButtonItem) => {
    const key = buttonKey(updated);
    setPendingButtons(buttons.map((b) => (buttonKey(b) === key ? updated : b)));
  };

  const handleButtonDelete = () => {
    if (selection?.kind !== "button") return;
    setPendingButtons(
      buttons.filter((b) => buttonKey(b) !== selection.buttonKey),
    );
    setSelection(null);
  };

  const handleSaveButtons = async () => {
    if (!selectedWindow) return;
    setIsSaving(true);
    try {
      const updated = await replaceButtons(
        selectedWindow.key,
        buttons.map(toButtonInput),
      );
      setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)));
      setPendingButtons(null);
      reloadEntries();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDiscardButtons = () => setPendingButtons(null);

  const canCreateWindow = permissions.includes("DIALOGS_WINDOWS_CREATE");
  const isWindowLimitReached =
    catalog !== null &&
    windows.filter((w) => w.kind === "custom").length >=
      catalog.custom_window_limit;
  const brokenUrlButton = catalog
    ? invalidUrlButton(buttons, catalog.variable_keys)
    : null;
  const limitProblem = buttonLimitProblem(buttons);
  const canResetAll = permissions.includes("DIALOGS_WINDOWS_RESET_ALL");

  const handleCreateWindow = async (name: string): Promise<boolean> => {
    try {
      const created = await createCustomWindow(name);
      setWindowsData([...windows, created]);
      setSelectedKey(created.key);
      toast.success(t("common.saved"));
      return true;
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      return false;
    }
  };

  const handleDeleteWindow = async (key: string) => {
    try {
      await deleteCustomWindow(key);
      setWindowsData(windows.filter((w) => w.key !== key));
      if (selectedKey === key) setSelectedKey(null);
      toast.success(t("dialogs.windowList.deleted"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleResetAll = async () => {
    setIsResetAllConfirmOpen(false);
    try {
      await resetAll();
      reloadWindows();
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      is_system: false,
    };
    setPendingButtons([...buttons, newButton]);
    setSelection({ kind: "button", buttonKey: buttonKey(newButton) });
  };

  const handleSelectWindow = (key: string) => {
    if (isDirty) {
      setPendingWindowSwitch(key);
      return;
    }
    setSelectedKey(key);
  };

  const backToWindow = () => setSelection(null);

  function renderInspector() {
    if (!selectedWindow) return null;
    const button = selection?.kind === "button" ? buttons.find((b) => buttonKey(b) === selection.buttonKey) : undefined;
    if (selection?.kind === "text" && previewLocale !== null && entriesState.kind === "ready") {
      return (
        <>
          <InspectorHeader title={t("dialogs.inspector.textTitle")} subtitle={windowLabel(selectedWindow)} onBack={backToWindow} />
          <InspectorDivider />
          <TextEditorPanel
            textKey={selectedWindow.text_keys[0] ?? ""}
            entries={entries}
            activeLocale={previewLocale}
            variables={variableOptions(
              catalog,
              catalog?.text_variable_keys ?? [],
              catalog?.window_text_variable_keys[selectedWindow.key],
            )}
            multiline
            html
            emojiInsert
            // Without a banner the window is a plain message, which cannot be
            // empty; with one it is a photo caption, which is shorter.
            required={!selectedWindow.banner_name}
            maxLength={selectedWindow.banner_name ? MAX_CAPTION_LENGTH : MAX_TEXT_LENGTH}
            canUpdate={permissions.includes("DIALOGS_TEXT_UPDATE")}
            canReset={permissions.includes("TRANSLATIONS_RESET")}
            onSaved={handleEntrySaved}
          />
        </>
      );
    }
    if (button && catalog !== null && previewLocale !== null && entriesState.kind === "ready") {
      return (
        <ButtonInspector
          button={button}
          windowLabel={windowLabel(selectedWindow)}
          windowLabelOf={(key) => {
            const target = windows.find((w) => w.key === key);
            return target ? windowLabel(target) : key;
          }}
          catalog={catalog}
          entries={entries}
          activeLocale={previewLocale}
          canEditText={permissions.includes("DIALOGS_TEXT_UPDATE")}
          canResetText={permissions.includes("TRANSLATIONS_RESET")}
          canEditButtons={canEditButtons}
          onEntrySaved={handleEntrySaved}
          onChange={handleButtonChange}
          onDelete={handleButtonDelete}
          onBack={backToWindow}
        />
      );
    }
    return (
      <WindowInspector
        window={selectedWindow}
        label={windowLabel(selectedWindow)}
        activeLocale={previewLocale}
        banner={banner}
        isUnreachable={unreachableKeys.has(selectedWindow.key)}
        onBannerChanged={() => setBannerNonce((nonce) => nonce + 1)}
        onWindowUpdated={(updated) => setWindowsData(windows.map((w) => (w.key === updated.key ? updated : w)))}
        onDelete={() => void handleDeleteWindow(selectedWindow.key)}
      />
    );
  }

  const handleExport = async () => {
    try {
      const payload = await exportDialogs();
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `dialogs-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleFileChosen = async (file: File) => {
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        !("version" in parsed)
      ) {
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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <Section
      flush
      {...sectionProps}
      aside={
        <>
          {permissions.includes("DIALOGS_EXPORT") && (
            <Button variant="glass" icon={Download} onClick={() => void handleExport()}>
              {t("dialogs.toolbar.export")}
            </Button>
          )}
          {permissions.includes("DIALOGS_IMPORT") && (
            <Button variant="glass" icon={Upload} onClick={() => fileInputRef.current?.click()}>
              {t("dialogs.toolbar.import")}
            </Button>
          )}
          {canResetAll && (
            <Button variant="glassDanger" icon={RotateCcw} onClick={() => setIsResetAllConfirmOpen(true)}>
              {t("dialogs.inspector.resetAll")}
            </Button>
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
        </>
      }
    >
      <div className="flex flex-col gap-4 p-4">
        <WindowSwitcher
          windows={windows}
          labelOf={windowLabel}
          selectedKey={selectedKey}
          onSelect={handleSelectWindow}
          canCreate={canCreateWindow && !isWindowLimitReached}
          isLimitReached={isWindowLimitReached}
          unreachableKeys={unreachableKeys}
          dirtyKey={isDirty ? selectedKey : null}
          onCreate={handleCreateWindow}
          aside={
            activeLocales.length > 1 &&
            previewLocale !== null && (
              <SegmentedPills
                compact
                value={previewLocale}
                onChange={setPreviewLocale}
                options={activeLocales.map((locale) => ({ value: locale, label: localeLabel(locale, i18n.language) }))}
              />
            )
          }
        />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          {selectedWindow ? (
            <DialogCanvas
              window={selectedWindow}
              buttons={buttons}
              textByKey={textByKey}
              bannerUrl={banner?.url ?? null}
              selection={selection}
              onSelect={setSelection}
              canEditButtons={canEditButtons}
              onReorderButtons={setPendingButtons}
              onAddButton={canEditButtons && catalog ? handleAddButton : undefined}
            />
          ) : (
            <div />
          )}
          {selectedWindow && (
            <div className={`${GLASS_INNER_CARD_CLASS} flex flex-col gap-4 p-4`}>
              {renderInspector()}
              {isDirty && canEditButtons && (
                <div className="-mx-4 flex flex-col gap-2 border-t border-white/[0.08] px-4">
                  <SaveFooter
                    dirty
                    saving={isSaving}
                    disabled={brokenUrlButton !== null || limitProblem !== null}
                    onSave={() => void handleSaveButtons()}
                    beside={
                      <Button variant="glass" onClick={handleDiscardButtons}>
                        {t("dialogs.inspector.buttonsDiscard")}
                      </Button>
                    }
                  />
                  {brokenUrlButton !== null && <p className="text-xs text-error">{t("dialogs.inspector.buttonUrlInvalidGrid")}</p>}
                  {limitProblem !== null && (
                    <p className="text-xs text-error">
                      {limitProblem.kind === "row"
                        ? t("dialogs.inspector.buttonsRowLimit", { max: limitProblem.max })
                        : t("dialogs.inspector.buttonsTotalLimit", { max: limitProblem.max })}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {pendingWindowSwitch && (
        <ConfirmDialog
          title={t("dialogs.inspector.buttonsDiscardTitle")}
          message={t("dialogs.inspector.discardSwitchConfirm")}
          confirmLabel={t("dialogs.inspector.discardSwitchConfirmButton")}
          cancelLabel={t("common.cancel")}
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
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleImportConfirmed()}
          onCancel={() => setPendingImport(null)}
        />
      )}
      {isResetAllConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetAllTitle")}
          message={t("dialogs.inspector.resetAllConfirm")}
          confirmLabel={t("dialogs.inspector.resetAllConfirmButton")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleResetAll()}
          onCancel={() => setIsResetAllConfirmOpen(false)}
        />
      )}
    </Section>
  );
}
