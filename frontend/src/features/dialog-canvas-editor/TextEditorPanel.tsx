import { RotateCcw } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { sentTextLength, splitTextKey, updateDialogText } from "@entities/dialogs/api";
import type { VariableOption } from "@entities/dialogs/api";
import { getErrorMessage } from "@shared/api/http";
import { resetTranslation } from "@entities/translations/api";
import type { TranslationEntry } from "@entities/translations/api";
import { toast } from "@shared/lib/toast";
import { EmojiPicker, type PickedEmoji } from "@entities/emoji-packs/EmojiPicker";
import { windowTextLength } from "@features/dialog-canvas-editor/fluent-select";
import { FormatToolbar } from "@features/dialog-canvas-editor/FormatToolbar";
import { RichTextField, type RichTextFieldHandle } from "@features/dialog-canvas-editor/RichTextField";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";
import { Button } from "@shared/ui/Button";
import { TEXT_TOOLBAR_CLASS, TEXT_TOOLBAR_DIVIDER_CLASS } from "@shared/ui/classes";
import { Input } from "@shared/ui/glass/Input";

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
  /** The text is Telegram HTML: formatting toolbar, length counted without tags. */
  html?: boolean;
  /** Text takes emoji inline, at the cursor. A premium one becomes the markup
   * the bot turns into a custom_emoji entity. */
  emojiInsert?: boolean;
  /** Replaces the emoji picker inside the field; the button label puts its icon picker there. */
  fieldAction?: ReactNode;
  /** Telegram rejects a button, or a message without a banner, with no text. */
  required?: boolean;
  /** Telegram's limit for this text, counted the way it counts. */
  maxLength?: number;
  /** A banner's caption limit: past it the bot sends the window without the banner, so only a warning. */
  captionLength?: number;
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
  html = false,
  emojiInsert = false,
  fieldAction,
  required = false,
  maxLength,
  captionLength,
  save = updateDialogText,
  onSaved,
}: TextEditorPanelProps) {
  const { t } = useTranslation();
  const { messageId, attributeId } = splitTextKey(textKey);
  const entry = entries.find(
    (e) => e.locale === activeLocale && e.message_id === messageId && e.attribute_id === attributeId,
  );
  const [draft, setDraft] = useState(entry?.value ?? "");
  const draftLength = html ? windowTextLength(draft) : sentTextLength(draft);
  const isTooLong = maxLength !== undefined && draftLength > maxLength;
  const isOverCaption = !isTooLong && captionLength !== undefined && draftLength > captionLength;
  // the caption limit until the text passes it, then the hard one
  const shownLimit = captionLength !== undefined && !isOverCaption && !isTooLong ? captionLength : maxLength;
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
    // entry.value changes only server-side (save/reset), never on a keystroke
  }, [textKey, activeLocale, entry?.value]);

  const hasVariables = variables.length > 0;
  const emoji =
    fieldAction ??
    (emojiInsert && <EmojiPicker current={null} disabled={!canUpdate} onPick={handleEmojiPick} onClear={() => undefined} />);
  const pickers = (hasVariables || emoji) && (
    <>
      {hasVariables && (
        <VariablePicker
          variables={variables}
          format={(name) => `{ $${name} }`}
          onPick={insertAtCursor}
          disabled={!canUpdate}
        />
      )}
      {emoji}
    </>
  );

  const isChanged = draft !== (entry?.value ?? "");
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
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {multiline ? (
        <div className="glass-well relative overflow-hidden rounded-[18px] ring-inset focus-within:ring-1 focus-within:ring-primary">
          <div className={TEXT_TOOLBAR_CLASS}>
            {html && (
              <>
                <FormatToolbar fieldRef={richFieldRef} disabled={!canUpdate} />
                <span className={TEXT_TOOLBAR_DIVIDER_CLASS} />
              </>
            )}
            {pickers}
          </div>
          <RichTextField
            ref={richFieldRef}
            value={draft}
            disabled={!canUpdate}
            onChange={setDraft}
            className="min-h-40 w-full px-3.5 pb-10 pt-3 text-sm leading-relaxed text-foreground outline-none"
          />
          {maxLength !== undefined && (
            <span
              className={`glass-control pointer-events-none absolute bottom-3 right-3 rounded-full px-2 py-0.5 text-xs tabular-nums ${
                isTooLong ? "text-error" : isOverCaption ? "text-warning" : "text-muted-foreground"
              }`}
            >
              {`${draftLength} / ${shownLimit}`}
            </span>
          )}
        </div>
      ) : (
        <Input
          ref={fieldRef}
          value={draft}
          disabled={!canUpdate}
          aria-invalid={isTooLong || undefined}
          onChange={(event) => setDraft(event.target.value)}
          end={pickers && <span className="flex items-center gap-0.5 pr-0.5">{pickers}</span>}
        />
      )}
      {isTooLong && (
        <p className="text-xs text-error">
          {t("dialogs.inspector.textTooLong", { length: draftLength, max: maxLength })}
        </p>
      )}
      {isOverCaption && (
        <p className="text-xs text-warning">{t("dialogs.inspector.textOverCaption", { max: captionLength })}</p>
      )}
      {/* nothing to save or reset: no buttons under the field */}
      {((canUpdate && isChanged) || canShowReset) && (
        <div className="flex gap-2">
          {canUpdate && isChanged && (
            <Button
              variant="glassAccent"
              disabled={(required && draft.trim() === "") || isTooLong}
              onClick={() => void handleSave()}
            >
              {t(canShowReset ? "common.save" : "dialogs.inspector.textSave")}
            </Button>
          )}
          {canShowReset && (
            <Button variant="glass" icon={RotateCcw} isLoading={isResetting} onClick={() => void handleReset()}>
              {t("common.reset")}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
