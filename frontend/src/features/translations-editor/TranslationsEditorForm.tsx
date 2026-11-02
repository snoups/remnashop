import { ChevronRight, CircleAlert, Download, Languages, RotateCcw, Upload } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { iconIdTextKey, iconTextKey, listWindows, windowTextKeys } from "@entities/dialogs/api";
import { LocalesManager } from "@features/translations-editor/LocalesManager";
import { Button } from "@shared/ui/Button";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { PillTabs } from "@shared/ui/PillTabs";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import {
  exportTranslations,
  importTranslations,
  listActiveLocales,
  listTranslations,
  resetAllTranslations,
  type TranslationEntry,
  type TranslationsExportPayload,
  updateTranslation,
} from "@entities/translations/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Collapse } from "@shared/ui/Collapse";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { localeLabel } from "@shared/i18n/locale-label";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { Section } from "@shared/ui/glass/Section";
import { Pressable } from "@shared/ui/Pressable";

/** Every other locale starts life as a copy of this one. */
const SOURCE_LOCALE = "en";

/** Key prefixes are the project's grouping: msg-, btn-, ntf- and so on. */
function groupOf(key: string): string {
  const dash = key.indexOf("-");
  return dash === -1 ? key : key.slice(0, dash);
}

function toGroups(
  entries: TranslationEntry[],
  excludeKeys: Set<string>,
): { group: string; keys: string[] }[] {
  // `btn-menu = ` with nothing but attributes under it is a Fluent grouping
  // header, not a string anyone edits.
  const grouping = new Set(entries.filter((e) => e.attribute_id).map((e) => e.message_id));
  const byGroup = new Map<string, Set<string>>();
  for (const entry of entries) {
    const key = entry.attribute_id ? `${entry.message_id}.${entry.attribute_id}` : entry.message_id;
    if (excludeKeys.has(key)) continue;
    if (!entry.attribute_id && grouping.has(entry.message_id)) continue;
    const group = groupOf(entry.message_id);
    const keys = byGroup.get(group) ?? new Set<string>();
    keys.add(key);
    byGroup.set(group, keys);
  }
  return [...byGroup.entries()]
    .map(([group, keys]) => ({ group, keys: [...keys].sort() }))
    .sort((a, b) => a.group.localeCompare(b.group));
}

export function TranslationsEditorForm() {
  const { t, i18n } = useTranslation();
  const [windowsState] = useAsyncResource(listWindows);
  const [localesState, , setLocalesState] = useAsyncResource(listActiveLocales);
  const [entriesState, reloadEntries, setEntriesData] = useAsyncResource(listTranslations);
  const [pickedKey, setSelectedKey] = useState<string | null>(null);
  const [pickedLocale, setActiveLocale] = useState<string | null>(null);
  // a group stays as clicked, otherwise only the first one is expanded
  const [toggledGroups, setToggledGroups] = useState<Record<string, boolean>>({});
  const [pendingImport, setPendingImport] = useState<TranslationsExportPayload | null>(null);
  const [isResetAllConfirmOpen, setIsResetAllConfirmOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const permissions = usePermissions();

  const entries = entriesState.kind === "ready" ? entriesState.data : [];
  const activeLocales = localesState.kind === "ready" ? localesState.data.active : [];
  // A window's text, button labels and emoji are edited on the canvas; this
  // panel holds the rest: notifications, dynamic lists and flows with no
  // window yet.
  const onCanvas = new Set<string>();
  if (windowsState.kind === "ready") {
    for (const window of windowsState.data) {
      for (const key of windowTextKeys(window)) {
        onCanvas.add(key);
        onCanvas.add(iconTextKey(key));
        onCanvas.add(iconIdTextKey(key));
      }
    }
  }
  const groups = toGroups(entries, onCanvas);
  // nothing picked means the first of each; derived, so a disabled locale or a
  // key gone from the list can't stay selected
  const activeLocale = pickedLocale ?? activeLocales[0] ?? null;
  const selectedKey = pickedKey ?? groups[0]?.keys[0] ?? null;

  // A newly enabled locale starts as a copy of English, so "translated" is the
  // rows somebody has actually changed since.
  const englishValues = new Map(
    entries
      .filter((e) => e.locale === SOURCE_LOCALE)
      .map((e) => [`${e.message_id}.${e.attribute_id}`, e.value]),
  );
  const localeStats = activeLocales.map((locale) => {
    const rows = entries.filter((e) => e.locale === locale);
    return {
      locale,
      total: rows.length,
      translated: rows.filter(
        (e) => e.value !== englishValues.get(`${e.message_id}.${e.attribute_id}`),
      ).length,
    };
  });

  const untranslatedKeys = new Set(
    activeLocale === SOURCE_LOCALE
      ? []
      : entries
          .filter(
            (e) =>
              e.locale === activeLocale &&
              e.value === englishValues.get(`${e.message_id}.${e.attribute_id}`),
          )
          .map((e) => (e.attribute_id ? `${e.message_id}.${e.attribute_id}` : e.message_id)),
  );

  const isGroupCollapsed = (group: string) => toggledGroups[group] ?? group !== groups[0]?.group;

  const toggleGroup = (group: string) =>
    setToggledGroups((current) => ({ ...current, [group]: !isGroupCollapsed(group) }));

  const handleExport = async () => {
    try {
      const payload = await exportTranslations();
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `translations-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleFileChosen = async (file: File) => {
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (typeof parsed !== "object" || parsed === null || !("texts" in parsed)) {
        throw new Error("not a translations export");
      }
      setPendingImport(parsed as TranslationsExportPayload);
    } catch {
      toast.error(t("dialogs.texts.importInvalid"));
    }
  };

  const handleImportConfirmed = async () => {
    if (pendingImport === null) return;
    const payload = pendingImport;
    setPendingImport(null);
    try {
      const result = await importTranslations(payload);
      reloadEntries();
      toast.success(
        t("dialogs.texts.imported", { applied: result.applied, skipped: result.skipped }),
      );
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleResetAll = async () => {
    setIsResetAllConfirmOpen(false);
    try {
      await resetAllTranslations();
      reloadEntries();
      toast.success(t("dialogs.texts.resetAllDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleEntrySaved = (updated: TranslationEntry) => {
    if (entriesState.kind !== "ready") return;
    const next = entriesState.data.filter(
      (e) =>
        !(
          e.locale === updated.locale &&
          e.message_id === updated.message_id &&
          e.attribute_id === updated.attribute_id
        ),
    );
    next.push(updated);
    setEntriesData(next);
  };

  return (
    <Section
      flush
      className="min-h-0 flex-1"
      icon={Languages}
      title={t("dialogs.texts.title")}
      description={t("dialogs.texts.description")}
      aside={
        <>
          {permissions.includes("TRANSLATIONS_EXPORT") && (
            <Button variant="glass" icon={Download} onClick={() => void handleExport()}>
              {t("dialogs.toolbar.export")}
            </Button>
          )}
          {permissions.includes("TRANSLATIONS_IMPORT") && (
            <Button variant="glass" icon={Upload} onClick={() => fileInputRef.current?.click()}>
              {t("dialogs.toolbar.import")}
            </Button>
          )}
          {permissions.includes("TRANSLATIONS_RESET_ALL") && (
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
      <div className="flex min-h-0 flex-1 flex-col pt-4 lg:flex-row">
        <aside className="max-h-72 shrink-0 overflow-y-auto border-b border-white/[0.08] px-4 pb-4 lg:max-h-none lg:w-[27.7%] lg:overflow-y-visible lg:border-b-0 lg:pr-2">
          <div className="flex flex-col gap-1.5">
            {groups.map(({ group, keys }) => {
              const isCollapsed = isGroupCollapsed(group);
              return (
                <div key={group}>
                  <Pressable
                    type="button"
                    onClick={() => toggleGroup(group)}
                    className="group relative isolate flex h-[30px] w-full cursor-pointer items-center gap-1 rounded-full px-1.5 text-left text-[11px] uppercase leading-5 tracking-wide text-muted-foreground"
                  >
                    <motion.span
                      className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]"
                    />
                    <ChevronRight
                      className={`relative z-10 size-3 shrink-0 transition-transform ${isCollapsed ? "" : "rotate-90"}`}
                    />
                    <span className="relative z-10 truncate">{group}</span>
                    {keys.some((key) => untranslatedKeys.has(key)) && (
                      <CircleAlert
                        className="relative z-10 size-3 shrink-0 text-warning"
                      />
                    )}
                    <span className="relative z-10 ml-auto text-[11px] tabular-nums opacity-70">
                      {keys.length}
                    </span>
                  </Pressable>
                  <Collapse open={!isCollapsed} className="ml-[13px] mt-1 flex flex-col gap-0.5 border-l border-white/[0.08] pl-1.5">
                    {keys.map((key) => (
                      <Pressable
                        key={key}
                        type="button"
                        onClick={() => setSelectedKey(key)}
                        className="group relative isolate flex min-w-0 cursor-pointer items-center rounded-full"
                      >
                        <motion.span
                          className={`absolute inset-0 rounded-full transition-colors ${
                            key === selectedKey ? "bg-accent" : "group-hover:bg-white/[0.04]"
                          }`}
                        />
                        <span
                          className={`relative z-10 min-w-0 flex-1 truncate px-2.5 text-left font-mono text-[12px] leading-[30px] ${
                            key === selectedKey
                              ? "font-medium text-primary"
                              : "text-foreground/80"
                          }`}
                        >
                          {key}
                        </span>
                        {untranslatedKeys.has(key) && (
                          <CircleAlert
                            className="relative z-10 mr-2.5 size-3.5 shrink-0 text-warning"
                          />
                        )}
                      </Pressable>
                    ))}
                  </Collapse>
                </div>
              );
            })}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col items-center gap-3 overflow-y-auto px-2 pb-4">
          {entriesState.kind === "loading" && <Spinner size="card" />}
          {entriesState.kind === "error" && (
            <ErrorState text={t("common.loadError")} />
          )}
          {activeLocales.length > 1 && (
            <div className="w-full max-w-sm">
              <PillTabs
                items={activeLocales.map((locale) => ({
                  key: locale,
                  label: localeLabel(locale, i18n.language),
                }))}
                activeKey={activeLocale}
                onSelect={setActiveLocale}
                blurred={false}
              />
            </div>
          )}
          {selectedKey !== null && activeLocale !== null && (
            <Card className="w-full max-w-sm">
              <TextEditorPanel
                // Remounts on key or locale change so the draft never carries
                // one string's text over to another.
                key={`${selectedKey}:${activeLocale}`}
                textKey={selectedKey}
                entries={entries}
                activeLocale={activeLocale}
                variables={[]}
                multiline
                blurred={false}
                emojiInsert
                canUpdate={permissions.includes("TRANSLATIONS_UPDATE")}
                canReset={permissions.includes("TRANSLATIONS_RESET")}
                save={updateTranslation}
                onSaved={handleEntrySaved}
              />
            </Card>
          )}
        </div>

        <aside className="flex shrink-0 flex-col gap-3 border-t border-white/[0.08] pr-4 pb-4 lg:w-[27.7%] lg:border-t-0">
          {localesState.kind === "ready" && (
            <div>
              <LocalesManager
                locales={localesState.data}
                onChange={(locales) => {
                  setLocalesState(locales);
                  reloadEntries();
                }}
              />
            </div>
          )}
          {localeStats.length > 0 && (
            <Card variant="bare">
              <ul className="flex flex-col divide-y divide-white/[0.06]">
                {localeStats.map(({ locale, total, translated }) => (
                  <li key={locale} className="flex flex-wrap items-baseline gap-x-2 px-3.5 py-2.5">
                    <span className="truncate text-[13px] font-medium text-foreground">
                      {localeLabel(locale, i18n.language)}
                    </span>
                    <span className="ml-auto shrink-0 text-[12px] tabular-nums text-muted-foreground">
                      {locale === SOURCE_LOCALE
                        ? t("dialogs.texts.localeSource", { total })
                        : t("dialogs.texts.localeTranslated", { translated, total })}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>

      {pendingImport !== null && (
        <ConfirmDialog
          title={t("dialogs.toolbar.import")}
          icon={Upload}
          message={t("dialogs.texts.importConfirm")}
          confirmLabel={t("dialogs.toolbar.importConfirmButton")}
          cancelLabel={t("common.cancel")}
          onConfirm={() => void handleImportConfirmed()}
          onCancel={() => setPendingImport(null)}
        />
      )}
      {isResetAllConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetAllTitle")}
          message={t("dialogs.texts.resetAllConfirm")}
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
