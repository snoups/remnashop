import { Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { sentTextLength, splitTextKey, updateDialogText } from "@entities/dialogs/api";
import type { VariableOption } from "@entities/dialogs/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { resetTranslation } from "@entities/translations/api";
import type { TranslationEntry } from "@entities/translations/api";
import { toast } from "@shared/lib/toast";
import { EmojiPicker, type PickedEmoji } from "@shared/ui/EmojiPicker";
import { EDITOR_FIELD_CLASSNAME } from "@features/dialog-canvas-editor/field-classname";
import { RichTextField, type RichTextFieldHandle } from "@features/dialog-canvas-editor/RichTextField";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";

// right padding a one-line field reserves for the 26px pickers inside it
const ACTION_PADDING = ["", "pr-10", "pr-[68px]"] as const;

interface TextEditorPanelProps {
  textKey: string;
  entries: TranslationEntry[];
  activeLocale: string;
  variables: VariableOption[];
  canUpdate: boolean;
  canReset: boolean;
  /** A window body is a Telegram message and may have paragraphs; a button
   * label is one line. */
  multiline?: boolean;
  /** Text takes emoji inline, at the cursor. A premium one becomes the markup
   * the bot turns into a custom_emoji entity. */
  emojiInsert?: boolean;
  /** Rendered inside the field, in the corner the text never reaches -- the
   * button label puts its icon picker there. */
  fieldAction?: ReactNode;
  /** Telegram rejects a button, or a message without a banner, with no text. */
  required?: boolean;
  /** Telegram's limit for this text, counted the way it counts. */
  maxLength?: number;
  /** Dialog texts go through the dialogs endpoint, which allows newlines and
   * rejects keys outside the catalog; everything else goes through the general
   * translations one. */
  save?: (
    locale: string,
    messageId: string,
    attributeId: string,
    value: string,
  ) => Promise<{ locale: string; message_id: string; value: string; default_value: string }>;
  onSaved: (entry: TranslationEntry) => void;
}

export function TextEditorPanel({
  textKey,
  entries,
  activeLocale,
  variables,
  canUpdate,
  canReset,
  multiline = false,
  emojiInsert = false,
  fieldAction,
  required = false,
  maxLength,
  save = updateDialogText,
  onSaved,
}: TextEditorPanelProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const { messageId, attributeId } = splitTextKey(textKey);
  const entry = entries.find(
    (e) => e.locale === activeLocale && e.message_id === messageId && e.attribute_id === attributeId,
  );
  const [draft, setDraft] = useState(entry?.value ?? "");
  const draftLength = sentTextLength(draft);
  const isTooLong = maxLength !== undefined && draftLength > maxLength;
  const fieldRef = useRef<HTMLInputElement>(null);
  const richFieldRef = useRef<RichTextFieldHandle>(null);

  const insertAtCursor = (snippet: string) => {
    if (multiline) {
      richFieldRef.current?.insert(snippet);
      return;
    }
    const field = fieldRef.current;
    const at = field?.selectionStart ?? draft.length;
    setDraft((current) => `${current.slice(0, at)}${snippet}${current.slice(at)}`);
  };

  const handleEmojiPick = (picked: PickedEmoji) => {
    insertAtCursor(
      "glyph" in picked
        ? picked.glyph
        : // The glyph stays in the text as the fallback Telegram shows to
          // anyone the custom emoji does not render for.
          `[${picked.fallback}](emoji:${picked.customEmojiId})`,
    );
  };

  useEffect(() => {
    setDraft(entry?.value ?? "");
    // Re-syncs the draft whenever the selection or locale changes, or a save/reset
    // brings back a new entry.value -- but not on every keystroke (entry.value only
    // changes server-side).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textKey, activeLocale, entry?.value]);

  const hasVariables = variables.length > 0;
  const actionCount = Number(hasVariables) + Number(Boolean(fieldAction) || emojiInsert);

  const canShowReset = canReset && entry !== undefined && entry.value !== entry.default_value;

  const handleSave = async () => {
    try {
      const updated = await save(activeLocale, messageId, attributeId, draft);
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

  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      const reset = await resetTranslation(activeLocale, messageId, attributeId);
      onSaved(reset);
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div>
      <div className="relative">
        {multiline ? (
          <RichTextField
            ref={richFieldRef}
            value={draft}
            disabled={!canUpdate}
            onChange={setDraft}
            className="min-h-36 w-full resize-y overflow-auto rounded-lg border border-glass-border bg-white/[0.03] px-2.5 pb-9 pt-1.5 text-[13px] text-foreground outline-none backdrop-blur-md transition-colors hover:bg-white/[0.06] focus:border-primary"
          />
        ) : (
          <input
            ref={fieldRef}
            type="text"
            value={draft}
            disabled={!canUpdate}
            onChange={(event) => setDraft(event.target.value)}
            className={`${EDITOR_FIELD_CLASSNAME} border-glass-border ${ACTION_PADDING[actionCount]}`}
          />
        )}
        {/* Anchored where the text cannot reach it: the field reserves that
            padding above. right-5 on the multi-line field keeps the resize grip clear. */}
        <div
          className={`absolute flex items-center gap-1 ${multiline ? "bottom-2 right-5" : "right-2 top-1/2 -translate-y-1/2"}`}
        >
          {hasVariables && (
            <VariablePicker
              variables={variables}
              format={(name) => `{ $${name} }`}
              onPick={insertAtCursor}
              disabled={!canUpdate}
            />
          )}
          {fieldAction ??
            (emojiInsert && (
              <EmojiPicker
                current={null}
                disabled={!canUpdate}
                onPick={handleEmojiPick}
                onClear={() => undefined}
              />
            ))}
        </div>
      </div>
      {isTooLong && (
        <p className="mt-1 text-[11.5px] text-error">
          {t("dialogs.inspector.textTooLong", { length: draftLength, max: maxLength })}
        </p>
      )}
      <div className="mt-2 flex gap-2">
        {canUpdate && (
          <motion.button
            type="button"
            disabled={
              draft === (entry?.value ?? "") || (required && draft.trim() === "") || isTooLong
            }
            onClick={() => void handleSave()}
            {...bounceTap(bounceStrength)}
            className="h-9 flex-1 rounded-full border border-white/[0.12] px-3 text-[12px] text-foreground/80 hover:bg-white/[0.06] disabled:opacity-30"
          >
            {t(canShowReset ? "dialogs.inspector.textSaveShort" : "dialogs.inspector.textSave")}
          </motion.button>
        )}
        {canShowReset && (
          <motion.button
            type="button"
            onClick={() => void handleReset()}
            disabled={isResetting}
            {...bounceTap(bounceStrength)}
            className="flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full border border-white/[0.12] px-3 text-[12px] text-foreground/60 hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isResetting && <Loader2 className="size-3.5 animate-spin" />}
            {t("dialogs.inspector.textReset")}
          </motion.button>
        )}
      </div>
    </div>
  );
}
