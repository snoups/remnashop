import { Bold, Heading2, Italic, Link, List, ListOrdered, Quote } from "lucide-react";
import type { ComponentType } from "react";
import { useId, useRef } from "react";
import { useTranslation } from "react-i18next";

import { TEXT_LIMIT, TITLE_LIMIT, textLength, type TextDraft } from "@features/legal-documents-editor/legal-drafts";
import { formatDate } from "@shared/lib/relative-time";
import { FieldHint } from "@shared/ui/FieldHint";
import { TEXT_TOOLBAR_CLASS, TEXT_TOOLBAR_DIVIDER_CLASS } from "@shared/ui/classes";
import { Field } from "@shared/ui/glass/Field";
import { UrlPopoverButton } from "@features/dialog-canvas-editor/UrlPopoverButton";
import { Input } from "@shared/ui/glass/Input";
import { IconButton } from "@shared/ui/IconButton";
import { Switch } from "@shared/ui/glass/Switch";

interface MarkdownFormat {
  key: string;
  icon: ComponentType<{ className?: string }>;
  mark: string;
}

// what Telegram's rich messages and the cabinet's react-markdown (CommonMark, no GFM) both draw
const INLINE: MarkdownFormat[] = [
  { key: "bold", icon: Bold, mark: "**" },
  { key: "italic", icon: Italic, mark: "*" },
];
const BLOCKS: MarkdownFormat[] = [
  { key: "heading", icon: Heading2, mark: "## " },
  { key: "list", icon: List, mark: "- " },
  { key: "ordered", icon: ListOrdered, mark: "1. " },
  { key: "quote", icon: Quote, mark: "> " },
];
const URL_RE = /^https?:\/\/\S+$/;

interface Props {
  value: TextDraft;
  onChange: (value: TextDraft) => void;
  /** an edit of a text customers already accepted */
  canReaccept: boolean;
  lastReacceptanceAt: string | null;
  canSet: boolean;
  busy: boolean;
}

export function LegalTextEditor({
  value,
  onChange,
  canReaccept,
  lastReacceptanceAt,
  canSet,
  busy,
}: Props) {
  const { t, i18n } = useTranslation();
  const { title, body } = value;
  const length = textLength(value);

  const id = useId();
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  // edits go through onChange, then the caret goes back over what was marked
  const apply = (next: string, start: number, end: number) => {
    onChange({ ...value, body: next });
    requestAnimationFrame(() => {
      bodyRef.current?.focus();
      bodyRef.current?.setSelectionRange(start, end);
    });
  };
  const wrap = (open: string, close: string) => {
    const field = bodyRef.current;
    if (!field) return;
    const { selectionStart: start, selectionEnd: end } = field;
    apply(body.slice(0, start) + open + body.slice(start, end) + close + body.slice(end), start + open.length, end + open.length);
  };
  // a block mark on every line the selection touches
  const prefixLines = (mark: string) => {
    const field = bodyRef.current;
    if (!field) return;
    const lineStart = body.lastIndexOf("\n", field.selectionStart - 1) + 1;
    const lines = body.slice(lineStart, field.selectionEnd).split("\n");
    const marked = lines.map((line, index) => (mark === "1. " ? `${index + 1}. ` : mark) + line).join("\n");
    apply(body.slice(0, lineStart) + marked + body.slice(field.selectionEnd), lineStart, lineStart + marked.length);
  };
  const tool = (format: MarkdownFormat, onClick: () => void) => (
    <IconButton
      key={format.key}
      size="7"
      disabled={!canSet}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      <format.icon className="size-4" />
    </IconButton>
  );

  return (
    <div className="flex flex-col gap-4">
      <Field label={t("settings.legal.titleLabel")} htmlFor={`${id}-title`} required>
        <Input
          id={`${id}-title`}
          value={title}
          maxLength={TITLE_LIMIT}
          disabled={!canSet}
          onChange={(event) => onChange({ ...value, title: event.target.value })}
        />
      </Field>
      <Field
        label={t("settings.legal.bodyLabel")}
        htmlFor={`${id}-body`}
        required
        hint={t("settings.legal.bodyHint", { limit: TEXT_LIMIT })}
      >
        {/* the broadcast text editor's look: a toolbar over the field, the length in its corner */}
        <div className="glass-well relative overflow-hidden rounded-[18px] ring-inset focus-within:ring-1 focus-within:ring-primary">
          <div className={TEXT_TOOLBAR_CLASS}>
            {INLINE.map((format) => tool(format, () => wrap(format.mark, format.mark)))}
            <UrlPopoverButton
              icon={Link}
              pattern={URL_RE}
              disabled={!canSet}
              onInsert={(url) => wrap("[", `](${url})`)}
            />
            <span className={TEXT_TOOLBAR_DIVIDER_CLASS} />
            {BLOCKS.map((format) => tool(format, () => prefixLines(format.mark)))}
          </div>
          <textarea
            ref={bodyRef}
            id={`${id}-body`}
            rows={16}
            value={body}
            disabled={!canSet}
            onChange={(event) => onChange({ ...value, body: event.target.value })}
            className="block w-full resize-none bg-transparent px-3.5 pb-10 pt-3 text-[13px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
          />
          <span
            className={`glass-control pointer-events-none absolute bottom-3 right-3 rounded-full px-2 py-0.5 text-[11px] tabular-nums ${
              length > TEXT_LIMIT ? "text-error" : "text-muted-foreground"
            }`}
          >
            {length} / {TEXT_LIMIT}
          </span>
        </div>
      </Field>
      {canSet && canReaccept && (
        <div className="flex items-center gap-3">
          <p className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] font-medium text-foreground">
            {t("settings.legal.reaccept")}
            <FieldHint text={t("settings.legal.reacceptHint")} />
          </p>
          <Switch checked={value.reaccept} onChange={(reaccept) => onChange({ ...value, reaccept })} disabled={busy} />
        </div>
      )}
      {lastReacceptanceAt && (
        <span className="text-[12px] text-muted-foreground">
          {t("settings.legal.lastReaccept", { date: formatDate(lastReacceptanceAt, i18n.language) })}
        </span>
      )}
    </div>
  );
}
