import { Bold, Code, EyeOff, Italic, Link, Quote, Strikethrough, Underline } from "lucide-react";
import type { ComponentType, RefObject } from "react";

import type { RichTextFieldHandle } from "@features/dialog-canvas-editor/RichTextField";
import { UrlPopoverButton } from "@features/dialog-canvas-editor/UrlPopoverButton";
import { IconButton } from "@shared/ui/IconButton";

interface Format {
  key: string;
  icon: ComponentType<{ className?: string }>;
  open: string;
  close: string;
}

const FORMATS: Format[] = [
  { key: "bold", icon: Bold, open: "<b>", close: "</b>" },
  { key: "italic", icon: Italic, open: "<i>", close: "</i>" },
  { key: "underline", icon: Underline, open: "<u>", close: "</u>" },
  { key: "strike", icon: Strikethrough, open: "<s>", close: "</s>" },
];

const TRAILING_FORMATS: Format[] = [
  { key: "code", icon: Code, open: "<code>", close: "</code>" },
  { key: "spoiler", icon: EyeOff, open: "<tg-spoiler>", close: "</tg-spoiler>" },
  { key: "quote", icon: Quote, open: "<blockquote>", close: "</blockquote>" },
];

const TELEGRAM_URL_RE = /^(https?|tg):\/\/\S+$/;

const escapeAttr = (value: string) => value.replace(/&/g, "&amp;").replace(/"/g, "&quot;");

interface FormatToolbarProps {
  fieldRef: RefObject<RichTextFieldHandle | null>;
  disabled: boolean;
}

export function FormatToolbar({ fieldRef, disabled }: FormatToolbarProps) {
  const button = ({ key, icon: Icon, open, close }: Format) => (
    <IconButton
      key={key}
      size="7"
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => fieldRef.current?.wrap(open, close)}
    >
      <Icon className="size-4" />
    </IconButton>
  );

  return (
    <>
      {FORMATS.map(button)}
      <UrlPopoverButton
        icon={Link}
        pattern={TELEGRAM_URL_RE}
        disabled={disabled}
        onInsert={(url) => fieldRef.current?.wrap(`<a href="${escapeAttr(url)}">`, "</a>")}
      />
      {TRAILING_FORMATS.map(button)}
    </>
  );
}
