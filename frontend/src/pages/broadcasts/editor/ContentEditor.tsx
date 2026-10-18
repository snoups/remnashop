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
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { FIELD_SURFACE_CLASS } from "@shared/ui/TextInput";

import { setText } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";
import { LocaleTabs } from "@pages/broadcasts/editor/LocaleTabs";

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
    <Card className="flex flex-col gap-3">
      <LocaleTabs
        title={t("broadcasts.editor.text")}
        form={form}
        onChange={onChange}
        activeLocale={activeLocale}
        onLocaleChange={onLocaleChange}
        botLocales={botLocales}
        disabled={disabled}
      />

      <div className={`overflow-hidden rounded-2xl ${FIELD_SURFACE_CLASS}`}>
        <div className="flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5">
          <FormatToolbar fieldRef={fieldRef} disabled={disabled} />
          <span className="mx-1.5 h-4 w-px bg-border" />
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
          className="min-h-48 w-full px-3.5 py-3 text-sm leading-relaxed text-foreground outline-none"
        />
        <div className="flex flex-wrap items-center gap-1.5 border-t border-border px-3 py-2">
          {BROADCAST_VARIABLES.map(({ name }) => (
            <ChoiceChip
              key={name}
              active={false}
              size="sm"
              disabled={disabled}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => fieldRef.current?.insert(formatVariable(name))}
            >
              {formatVariable(name)}
            </ChoiceChip>
          ))}
          <span
            className={`ml-auto text-[12px] tabular-nums ${length > limit ? "text-error" : "text-muted-foreground"}`}
          >
            {`${length} / ${limit}`}
            {hasMedia && ` · ${t("broadcasts.editor.withMedia")}`}
          </span>
        </div>
      </div>

      {children}
    </Card>
  );
}
