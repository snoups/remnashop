import { Bot, CircleCheck, Globe, Languages, Layers } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  removeLegalText,
  setLegalText,
  updateLegalDocument,
  type LegalChannel,
  type LegalDocument,
} from "@entities/legal/api";
import {
  draftKey,
  isChanged,
  isValid,
  KIND_ICONS,
  textSlot,
  type TextDraft,
} from "@features/legal-documents-editor/legal-drafts";
import { LegalTextEditor } from "@features/legal-documents-editor/LegalTextEditor";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { Button } from "@shared/ui/Button";
import { DialogTabs } from "@shared/ui/DialogTabs";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { ToggleCapsule } from "@shared/ui/glass/ToggleCapsule";
import { Modal } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const CHANNELS = [null, "BOT", "CABINET"] as const;

type Tab = "common" | LegalChannel;

interface Props {
  document: LegalDocument;
  locales: string[];
  /** the show-in-bot / show-in-cabinet switches */
  canUpdate: boolean;
  canSet: boolean;
  canRemove: boolean;
  /** after a save or a removal: the parent reloads the documents */
  onChanged: () => void;
  onClose: () => void;
}

export function LegalDocumentDialog({ onClose, ...props }: Props) {
  return (
    <Modal onClose={onClose} size="xl" scrollable>
      <LegalDocumentDialogBody {...props} />
    </Modal>
  );
}

function LegalDocumentDialogBody({ document, locales, canUpdate, canSet, canRemove, onChanged }: Omit<Props, "onClose">) {
  const { t } = useTranslation();
  const [visibility, setVisibility] = useState({ show_in_bot: document.show_in_bot, show_in_cabinet: document.show_in_cabinet });
  const visibilityChanged =
    visibility.show_in_bot !== document.show_in_bot || visibility.show_in_cabinet !== document.show_in_cabinet;
  const [tab, setTab] = useState<Tab>("common");
  const [locale, setLocale] = useState(locales[0]);
  // edits of every language and channel of this document, until saved
  const [drafts, setDrafts] = useState<Record<string, TextDraft>>({});
  const [busy, setBusy] = useState(false);
  const [contentRef, contentHeight] = useMeasuredHeight();

  const channel: LegalChannel | null = tab === "common" ? null : tab;
  const slot = textSlot(document, locale, channel);
  const key = draftKey(document.kind, locale, channel);
  const draft = drafts[key];
  const value = draft ?? { ...slot.baseline, reaccept: false };

  const pending = locales.flatMap((code) =>
    CHANNELS.flatMap((target) => {
      const item = drafts[draftKey(document.kind, code, target)];
      const itemSlot = textSlot(document, code, target);
      return item && isChanged(item, itemSlot.baseline) ? [{ code, target, item, itemSlot }] : [];
    }),
  );
  const isFilled = (code: string) =>
    document.texts.some((item) => item.locale === code && (item.channel === null || item.channel === channel)) ||
    pending.some((entry) => entry.code === code && (entry.target === null || entry.target === channel));
  const template = slot.template;
  const canInsertTemplate =
    canSet && !!template && (value.title !== template.title || value.body !== template.body);

  const dropDraft = (target: string) =>
    setDrafts((prev) => {
      const { [target]: _dropped, ...rest } = prev;
      return rest;
    });

  const save = async () => {
    setBusy(true);
    try {
      if (visibilityChanged) await updateLegalDocument(document.kind, visibility);
      for (const { code, target, item, itemSlot } of pending) {
        await setLegalText(document.kind, code, target, {
          title: item.title,
          body: item.body,
          requires_reacceptance: itemSlot.canReaccept && item.reaccept,
        });
        dropDraft(draftKey(document.kind, code, target));
      }
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const removeOverride = async (target: LegalChannel) => {
    setBusy(true);
    try {
      await removeLegalText(document.kind, locale, target);
      dropDraft(draftKey(document.kind, locale, target));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <DialogHeader icon={KIND_ICONS[document.kind]} title={t(`settings.legal.kinds.${document.kind}`)} />
      <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto p-4">
        {/* eases like the other dialogs when the reaccept switch or the channel's own-text row comes and goes */}
        {/* the height animation clips; 4px of room on every side (given back by the negative margin)
            keeps the fields' 2px focus ring inside the clip */}
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="-m-1 overflow-hidden px-1"
        >
          <div ref={contentRef} className="flex flex-col gap-4 py-1">
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <DialogTabs
                  activeKey={tab}
                  onSelect={setTab}
                  items={[
                    { key: "common", label: t("settings.legal.tabs.common"), icon: Layers },
                    { key: "BOT", label: t("settings.legal.tabs.BOT"), icon: Bot },
                    { key: "CABINET", label: t("settings.legal.tabs.CABINET"), icon: Globe },
                  ]}
                />
              </div>
              {locales.length > 1 && (
                <div className="w-32 shrink-0">
                  <SelectDropdown
                    value={locale}
                    onChange={setLocale}
                    icon={Languages}
                    glassPopover
                    size="lg"
                    placeholder=""
                    // ✓ marks a language the open channel already has a text in
                    options={locales.map((code) => ({
                      value: code,
                      label: code.toUpperCase(),
                      icon: isFilled(code) ? CircleCheck : undefined,
                    }))}
                  />
                </div>
              )}
            </div>
            <Field label={t("settings.legal.visibility")}>
              <div className="flex gap-2">
                <ToggleCapsule
                  icon={Bot}
                  label={t("settings.legal.tabs.BOT")}
                  // a channel with no text of its own nor a common one has nothing to show
                  checked={visibility.show_in_bot && hasTextFor(document, "BOT")}
                  onChange={(show_in_bot) => setVisibility((prev) => ({ ...prev, show_in_bot }))}
                  disabled={!canUpdate || busy || !hasTextFor(document, "BOT")}
                />
                <ToggleCapsule
                  icon={Globe}
                  label={t("settings.legal.tabs.CABINET")}
                  checked={visibility.show_in_cabinet && hasTextFor(document, "CABINET")}
                  onChange={(show_in_cabinet) => setVisibility((prev) => ({ ...prev, show_in_cabinet }))}
                  disabled={!canUpdate || busy || !hasTextFor(document, "CABINET")}
                />
              </div>
            </Field>
            <LegalTextEditor
              value={value}
              onChange={(next) => setDrafts((prev) => ({ ...prev, [key]: next }))}
              canReaccept={slot.canReaccept && isChanged(draft, slot.baseline)}
              lastReacceptanceAt={slot.own?.last_reacceptance_at ?? null}
              canSet={canSet}
              busy={busy}
            />
          </div>
        </motion.div>
      </div>
      {(canSet || canRemove || canUpdate) && (
        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.08] p-4">
          <div className="min-w-0 flex-1">
            {(pending.length > 0 || visibilityChanged) && (
              <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                <span className="size-1.5 shrink-0 rounded-full bg-warning" />
                {t("common.unsavedChanges")}
              </span>
            )}
          </div>
          {channel !== null && slot.hasOverride && canRemove && (
            <Button variant="glass" disabled={busy} onClick={() => void removeOverride(channel)}>
              {t("settings.legal.resetToCommon")}
            </Button>
          )}
          {canInsertTemplate && template && (
            <Button
              variant="glass"
              disabled={busy}
              onClick={() =>
                setDrafts((prev) => ({
                  ...prev,
                  [key]: { title: template.title, body: template.body, reaccept: value.reaccept },
                }))
              }
            >
              {t("settings.legal.insertTemplate")}
            </Button>
          )}
          {(canSet || canUpdate) && (
            <Button
              variant="glassAccent"
              disabled={busy || (pending.length === 0 && !visibilityChanged) || pending.some(({ item }) => !isValid(item))}
              onClick={() => void save()}
            >
              {busy ? t("common.saving") : t("common.save")}
            </Button>
          )}
        </div>
      )}
    </>
  );
}

// shown only once some text exists for the channel, its own or the common one
function hasTextFor(document: LegalDocument, channel: LegalChannel): boolean {
  return document.texts.some((item) => item.channel === null || item.channel === channel);
}
