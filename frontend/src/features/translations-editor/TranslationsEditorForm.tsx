import { CircleAlert, Download, Languages, RotateCcw, Upload } from "lucide-react";
import type { ParseKeys } from "i18next";
import { motion } from "motion/react";
import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { iconIdTextKey, iconTextKey, isIconTextKey, listWindows, windowTextKeys } from "@entities/dialogs/api";
import { ButtonIconPicker } from "@features/dialog-canvas-editor/ButtonIconPicker";
import { InspectorDivider, InspectorHeader } from "@features/dialog-canvas-editor/InspectorParts";
import { LocalesManager } from "@features/translations-editor/LocalesManager";
import { Button } from "@shared/ui/Button";
import { GLASS_INNER_CARD_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
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
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { localeLabel } from "@shared/i18n/locale-label";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Section } from "@shared/ui/glass/Section";
import { Pressable } from "@shared/ui/Pressable";

/** Every other locale starts life as a copy of this one. */
const SOURCE_LOCALE = "en";

type Area = "bot" | "notifications" | "reference";

/** Groups of each area in tab order; a key prefix not listed here becomes a tab of "bot" after them. */
const AREAS: Record<Area, string[]> = {
  bot: ["msg", "frg", "btn", "ntf-bot", "command", "inline"],
  notifications: ["ntf-customer", "ntf-admin", "ntf-telegram"],
  reference: ["gateway", "platform", "time"],
};
const KNOWN_GROUPS = new Set(Object.values(AREAS).flat());

/** Key prefixes are the project's grouping (msg-, btn-, ...); ntf- is split by audience. withValue: messages
 *  with text of their own; withTitle: notifications, whose .title is the push title. */
function groupOf(messageId: string, withValue: Set<string>, withTitle: Set<string>): string {
  const dash = messageId.indexOf("-");
  const prefix = dash === -1 ? messageId : messageId.slice(0, dash);
  if (prefix !== "ntf") return prefix;
  if (messageId.startsWith("ntf-customer-")) return "ntf-customer";
  // field labels and value names of admin notification cards
  if (messageId.startsWith("ntf-telegram-") && !withTitle.has(messageId)) return "ntf-telegram";
  // bot replies are attribute-only bundles: ntf-devices.deleted
  if (!withValue.has(messageId)) return "ntf-bot";
  return "ntf-admin";
}

const entryKey = (e: TranslationEntry) => (e.attribute_id ? `${e.message_id}.${e.attribute_id}` : e.message_id);

/** Button labels of windows outside the canvas: their icon is picked beside the label, not edited as a row. */
const isButtonLabelKey = (key: string) => key.startsWith("btn-") && !isIconTextKey(key);

export function TranslationsEditorForm() {
  const { t, i18n } = useTranslation();
  const underlineId = useId();
  const [windowsState] = useAsyncResource(listWindows);
  const [localesState, , setLocalesState] = useAsyncResource(listActiveLocales);
  const [entriesState, reloadEntries, setEntriesData] = useAsyncResource(listTranslations);
  const [area, setArea] = useState<Area>("bot");
  const [pickedGroup, setPickedGroup] = useState<string | null>(null);
  const [pickedKey, setPickedKey] = useState<string | null>(null);
  const [pickedLocale, setActiveLocale] = useState<string | null>(null);
  const [pendingImport, setPendingImport] = useState<TranslationsExportPayload | null>(null);
  const [isResetAllConfirmOpen, setIsResetAllConfirmOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const permissions = usePermissions();

  const entries = entriesState.kind === "ready" ? entriesState.data : [];
  const activeLocales = localesState.kind === "ready" ? localesState.data.active : [];
  // nothing picked means the first of each; derived, so a disabled locale or a
  // key gone from the list can't stay selected
  const activeLocale = pickedLocale ?? activeLocales[0] ?? null;

  // A window's text, button labels and emoji are edited on the canvas; this
  // editor holds the rest: notifications, dynamic lists and flows with no
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
  const withValue = new Set(entries.filter((e) => !e.attribute_id).map((e) => e.message_id));
  const withTitle = new Set(entries.filter((e) => e.attribute_id === "title").map((e) => e.message_id));

  // A newly enabled locale starts as a copy of English, so "translated" is the
  // rows somebody has actually changed since.
  const englishValues = new Map(entries.filter((e) => e.locale === SOURCE_LOCALE).map((e) => [entryKey(e), e.value]));
  const isUntranslated = (e: TranslationEntry) =>
    e.locale !== SOURCE_LOCALE && e.value === englishValues.get(entryKey(e));

  const byGroup = new Map<string, TranslationEntry[]>();
  for (const entry of entries) {
    const key = entryKey(entry);
    if (entry.locale !== activeLocale || onCanvas.has(key)) continue;
    if (key.startsWith("btn-") && isIconTextKey(key)) continue;
    const group = groupOf(entry.message_id, withValue, withTitle);
    byGroup.set(group, [...(byGroup.get(group) ?? []), entry]);
  }
  const groupsIn = (target: Area) => [
    ...AREAS[target].filter((group) => byGroup.has(group)),
    ...(target === "bot" ? [...byGroup.keys()].filter((group) => !KNOWN_GROUPS.has(group)).sort() : []),
  ];
  const groups = groupsIn(area);
  const group = pickedGroup !== null && groups.includes(pickedGroup) ? pickedGroup : (groups[0] ?? null);
  const keys = (group === null ? [] : (byGroup.get(group) ?? [])).sort((a, b) => entryKey(a).localeCompare(entryKey(b)));
  const selected = keys.find((e) => entryKey(e) === pickedKey) ?? keys[0] ?? null;
  const selectedKey = selected ? entryKey(selected) : null;
  const hasUntranslated = (target: string) => (byGroup.get(target) ?? []).some(isUntranslated);

  const localeProgress = (locale: string) => {
    const rows = entries.filter((e) => e.locale === locale);
    if (locale === SOURCE_LOCALE) return `${rows.length}`;
    return `${rows.filter((e) => !isUntranslated(e)).length}/${rows.length}`;
  };
  const groupLabel = (id: string) => (KNOWN_GROUPS.has(id) ? t(`dialogs.texts.groups.${id}` as ParseKeys) : id);
  // the key without its group's prefix: what tells it apart in the list
  const keyTail = (key: string) => {
    const prefix = group !== null && group.startsWith("ntf-") && key.startsWith(`${group}-`) ? group : key.split("-")[0];
    return key.slice(prefix.length + 1) || key;
  };

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
      {entriesState.kind === "loading" && <Spinner size="card" />}
      {entriesState.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {entriesState.kind === "ready" && (
        <div className="flex flex-col gap-4 p-4">
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SegmentedPills
                compact
                value={area}
                onChange={(next) => {
                  setArea(next);
                  setPickedGroup(null);
                  setPickedKey(null);
                }}
                options={(Object.keys(AREAS) as Area[]).map((item) => ({
                  value: item,
                  label: t(`dialogs.texts.areas.${item}`),
                  dot: groupsIn(item).some(hasUntranslated),
                }))}
              />
              <div className="flex flex-wrap items-center gap-2">
                {activeLocales.length > 1 && activeLocale !== null && (
                  <SegmentedPills
                    compact
                    value={activeLocale}
                    onChange={setActiveLocale}
                    options={activeLocales.map((locale) => ({
                      value: locale,
                      label: `${localeLabel(locale, i18n.language)} · ${localeProgress(locale)}`,
                    }))}
                  />
                )}
                {localesState.kind === "ready" && (
                  <LocalesManager
                    locales={localesState.data}
                    onChange={(locales) => {
                      setLocalesState(locales);
                      reloadEntries();
                    }}
                  />
                )}
              </div>
            </div>
            <div className="no-scrollbar flex gap-1 overflow-x-auto border-b border-white/[0.08] px-1">
              {groups.map((item) => {
                const isActive = item === group;
                return (
                  // no ripple: a tab strip, like the window editor's
                  <button
                    key={item}
                    type="button"
                    onClick={() => {
                      setPickedGroup(item);
                      setPickedKey(null);
                    }}
                    className={`group relative flex h-11 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors ${
                      isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {!isActive && (
                      <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full transition-colors group-hover:bg-white/20" />
                    )}
                    {groupLabel(item)}
                    <span className="text-xs tabular-nums opacity-60">{byGroup.get(item)?.length}</span>
                    {hasUntranslated(item) && <span className="size-1.5 rounded-full bg-warning" />}
                    {isActive && (
                      <motion.span
                        layoutId={underlineId}
                        transition={{ type: "spring", stiffness: 500, damping: 40 }}
                        className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-primary"
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
            {/* the scroll sits inside the card: on the card itself the scrollbar squares its rounded corners */}
            <div className={`${GLASS_INNER_CARD_CLASS} overflow-hidden`}>
              <div className="flex max-h-[560px] flex-col gap-0.5 overflow-y-auto p-1.5">
                {keys.map((entry) => {
                  const key = entryKey(entry);
                  return (
                    <Pressable
                      key={key}
                      type="button"
                      onClick={() => setPickedKey(key)}
                      className={`flex min-w-0 items-center gap-2 rounded-full px-2.5 text-left font-mono text-xs transition-colors ${
                        key === selectedKey ? "bg-accent font-medium text-primary" : "text-foreground/80 hover:bg-white/[0.04]"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate leading-[30px]">{key}</span>
                      {isUntranslated(entry) && <CircleAlert className="size-3.5 shrink-0 text-warning" />}
                    </Pressable>
                  );
                })}
              </div>
            </div>

            {selected !== null && selectedKey !== null && activeLocale !== null && (
              <div className={`${GLASS_INNER_CARD_CLASS} flex flex-col gap-4 p-4`}>
                <InspectorHeader title={keyTail(selectedKey)} subtitle={<span className="font-mono">{selectedKey}</span>} />
                <InspectorDivider />
                <TextEditorPanel
                  // Remounts on key or locale change so the draft never carries
                  // one string's text over to another.
                  key={`${selectedKey}:${activeLocale}`}
                  textKey={selectedKey}
                  entries={entries}
                  activeLocale={activeLocale}
                  variables={[]}
                  multiline
                  // window bodies and fragments are Telegram HTML, the rest plain text
                  html={selectedKey.startsWith("msg-") || selectedKey.startsWith("frg-")}
                  emojiInsert
                  canUpdate={permissions.includes("TRANSLATIONS_UPDATE")}
                  canReset={permissions.includes("TRANSLATIONS_RESET")}
                  save={updateTranslation}
                  onSaved={handleEntrySaved}
                  fieldAction={
                    isButtonLabelKey(selectedKey) ? (
                      <ButtonIconPicker
                        textKey={selectedKey}
                        entries={entries}
                        activeLocale={activeLocale}
                        disabled={!permissions.includes("TRANSLATIONS_UPDATE")}
                        save={updateTranslation}
                        onSaved={handleEntrySaved}
                      />
                    ) : undefined
                  }
                />
                {activeLocale !== SOURCE_LOCALE && englishValues.has(selectedKey) && (
                  <div className="flex flex-col gap-1 rounded-xl border border-dashed border-white/[0.12] px-3.5 py-2.5">
                    <span className="text-xs text-muted-foreground">
                      {t("dialogs.texts.source", { locale: localeLabel(SOURCE_LOCALE, i18n.language) })}
                    </span>
                    <span className="whitespace-pre-wrap text-sm text-muted-foreground">
                      {englishValues.get(selectedKey)}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

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
