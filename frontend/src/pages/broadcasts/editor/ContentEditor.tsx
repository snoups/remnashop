import { useRef } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { BROADCAST_VARIABLES } from "@entities/broadcasts/api";
import { MAX_CAPTION_LENGTH, MAX_TEXT_LENGTH, sentTextLength } from "@entities/dialogs/api";
import { EmojiPicker } from "@entities/emoji-packs/EmojiPicker";
import type { PickedEmoji } from "@entities/emoji-packs/EmojiPicker";
import { FormatToolbar } from "@features/dialog-canvas-editor/FormatToolbar";
import { RichTextField } from "@features/dialog-canvas-editor/RichTextField";
import type { RichTextFieldHandle } from "@features/dialog-canvas-editor/RichTextField";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";

import { setText } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";
import { LocaleTabs } from "@pages/broadcasts/editor/LocaleTabs";
import { TEXT_TOOLBAR_CLASS, TEXT_TOOLBAR_DIVIDER_CLASS } from "@shared/ui/classes";

const formatVariable = (name: string) => `{ $${name} }`;

interface ContentEditorProps {
  form: EditorForm;
  onChange: (form: EditorForm) => void;
  activeLocale: string;
  onLocaleChange: (locale: string) => void;
  /** the bot's active locales, the ones a text can be added for */
  botLocales: string[];
  hasMedia: boolean;
  disabled: boolean;
  /** the media block, under the text */
  children: ReactNode;
}

export function ContentEditor({
  form,
  onChange,
  activeLocale,
  onLocaleChange,
  botLocales,
  hasMedia,
  disabled,
  children,
}: ContentEditorProps) {
  const { t } = useTranslation();
  const fieldRef = useRef<RichTextFieldHandle>(null);
  const text = form.contents[activeLocale]?.text ?? "";
  const length = sentTextLength(text);
  const limit = hasMedia ? MAX_CAPTION_LENGTH : MAX_TEXT_LENGTH;

  const pickEmoji = (picked: PickedEmoji) =>
    fieldRef.current?.insert("glyph" in picked ? picked.glyph : `[${picked.fallback}](emoji:${picked.customEmojiId})`);

  return (
    // a body only: the page's content card (one Section for Telegram and email) frames it
    <div className="mt-4 flex flex-col gap-3">
      <LocaleTabs
        form={form}
        onChange={onChange}
        activeLocale={activeLocale}
        onLocaleChange={onLocaleChange}
        botLocales={botLocales}
        disabled={disabled}
      />

      <div className="glass-well relative overflow-hidden rounded-[18px] ring-inset focus-within:ring-1 focus-within:ring-primary">
        <div className={TEXT_TOOLBAR_CLASS}>
          <FormatToolbar fieldRef={fieldRef} disabled={disabled} />
          <span className={TEXT_TOOLBAR_DIVIDER_CLASS} />
          <VariablePicker
            variables={BROADCAST_VARIABLES}
            format={formatVariable}
            onPick={(token) => fieldRef.current?.insert(token)}
            disabled={disabled}
          />
          <EmojiPicker current={null} disabled={disabled} onPick={pickEmoji} onClear={() => undefined} />
        </div>
        <RichTextField
          ref={fieldRef}
          value={text}
          disabled={disabled}
          onChange={(value) => onChange(setText(form, activeLocale, value))}
          className="min-h-48 w-full px-3.5 pb-10 pt-3 text-sm leading-relaxed text-foreground outline-none"
        />
        {/* the length in the field's corner, as the glass TextArea's */}
        <span
          className={`glass-control pointer-events-none absolute bottom-3 right-3 rounded-full px-2 py-0.5 text-xs tabular-nums ${
            length > limit ? "text-error" : "text-muted-foreground"
          }`}
        >
          {`${length} / ${limit}`}
          {hasMedia && ` · ${t("broadcasts.editor.withMedia")}`}
        </span>
      </div>

      {children}
    </div>
  );
}
