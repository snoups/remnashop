import { Bold, Code, EyeOff, Italic, Languages, Link, Strikethrough, Trash2, Underline } from "lucide-react";
import { useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { BROADCAST_VARIABLES } from "@entities/broadcasts/api";
import { MAX_CAPTION_LENGTH, MAX_TEXT_LENGTH, sentTextLength } from "@entities/dialogs/api";
import { EmojiPicker } from "@entities/emoji-packs/EmojiPicker";
import type { PickedEmoji } from "@entities/emoji-packs/EmojiPicker";
import { RichTextField } from "@features/dialog-canvas-editor/RichTextField";
import type { RichTextFieldHandle } from "@features/dialog-canvas-editor/RichTextField";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";
import { localeLabel } from "@shared/i18n/locale-label";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { FIELD_SURFACE_CLASS, TextInput } from "@shared/ui/TextInput";

import { addLocale, removeLocale, setText } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";

const formatVariable = (name: string) => `{ $${name} }`;

const FORMATS: { key: string; icon: ComponentType<{ className?: string }>; open: string; close: string }[] = [
  { key: "bold", icon: Bold, open: "<b>", close: "</b>" },
  { key: "italic", icon: Italic, open: "<i>", close: "</i>" },
  { key: "underline", icon: Underline, open: "<u>", close: "</u>" },
  { key: "strike", icon: Strikethrough, open: "<s>", close: "</s>" },
];

const escapeAttr = (value: string) => value.replace(/&/g, "&amp;").replace(/"/g, "&quot;");

function LinkButton({ disabled, onInsert }: { disabled: boolean; onInsert: (url: string) => void }) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [url, setUrl] = useState("https://");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  useClickOutside<HTMLElement>([triggerRef, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll<HTMLElement>(isOpen, popoverRef, () => setIsOpen(false));

  const submit = () => {
    if (!/^(https?|tg):\/\/\S+$/.test(url.trim())) return;
    onInsert(url.trim());
    setIsOpen(false);
  };

  return (
    <>
      <IconButton
        ref={triggerRef}
        size="7"
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          setUrl("https://");
          setIsOpen(!isOpen);
        }}
      >
        <Link className="size-4" />
      </IconButton>
      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="left"
        maxHeight={60}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-80 p-2"
      >
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <TextInput
            autoFocus
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://"
            className="min-w-0 flex-1"
          />
          <Button variant="secondary" size="field" type="submit">
            {t("common.add")}
          </Button>
        </form>
      </PortalPopover>
    </>
  );
}

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
  const { t, i18n } = useTranslation();
  const fieldRef = useRef<RichTextFieldHandle>(null);
  const locales = Object.keys(form.contents);
  const text = form.contents[activeLocale]?.text ?? "";
  const length = sentTextLength(text);
  const limit = hasMedia ? MAX_CAPTION_LENGTH : MAX_TEXT_LENGTH;
  const missing = botLocales.filter((locale) => !locales.includes(locale));
  const defaultCode = form.default_locale.toUpperCase();

  const pickEmoji = (picked: PickedEmoji) =>
    fieldRef.current?.insert("glyph" in picked ? picked.glyph : `[${picked.fallback}](emoji:${picked.customEmojiId})`);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${EYEBROW_CLASS} mr-1.5`}>{t("broadcasts.editor.text")}</span>
        <div className="w-fit max-w-full">
          <PillTabs
            items={locales.map((locale) => ({
              key: locale,
              label: (
                <span className="flex items-center gap-1.5">
                  {locale.toUpperCase()}
                  {locale === form.default_locale && (
                    <span className="text-[10px] opacity-80">{t("broadcasts.editor.defaultLocale")}</span>
                  )}
                </span>
              ),
            }))}
            activeKey={activeLocale}
            onSelect={onLocaleChange}
          />
        </div>
        {activeLocale !== form.default_locale && (
          <IconButton
            size="8"
            tone="danger"
            disabled={disabled}
            onClick={() => {
              onChange(removeLocale(form, activeLocale));
              onLocaleChange(form.default_locale);
            }}
          >
            <Trash2 className="size-4" />
          </IconButton>
        )}
        {missing.length > 0 && (
          <div className="w-44">
            <SelectDropdown
              value=""
              size="compact"
              icon={Languages}
              disabled={disabled}
              placeholder={t("broadcasts.editor.addLocale")}
              options={missing.map((locale) => ({ value: locale, label: localeLabel(locale, i18n.language) }))}
              onChange={(locale) => {
                onChange(addLocale(form, locale));
                onLocaleChange(locale);
              }}
            />
          </div>
        )}
        <span className="ml-auto text-[12px] text-muted-foreground">
          {t("broadcasts.editor.fallbackHint", { locale: defaultCode })}
        </span>
      </div>

      <div className={`overflow-hidden rounded-2xl ${FIELD_SURFACE_CLASS}`}>
        <div className="flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5">
          {FORMATS.map(({ key, icon: Icon, open, close }) => (
            <IconButton
              key={key}
              size="7"
              disabled={disabled}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => fieldRef.current?.wrap(open, close)}
            >
              <Icon className="size-4" />
            </IconButton>
          ))}
          <LinkButton
            disabled={disabled}
            onInsert={(url) => fieldRef.current?.wrap(`<a href="${escapeAttr(url)}">`, "</a>")}
          />
          <IconButton
            size="7"
            disabled={disabled}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => fieldRef.current?.wrap("<code>", "</code>")}
          >
            <Code className="size-4" />
          </IconButton>
          <IconButton
            size="7"
            disabled={disabled}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => fieldRef.current?.wrap("<tg-spoiler>", "</tg-spoiler>")}
          >
            <EyeOff className="size-4" />
          </IconButton>
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
