import { useTranslation } from "react-i18next";

import { TEXT_LIMIT, TITLE_LIMIT, textLength, type TextDraft } from "@features/legal-documents-editor/legal-drafts";
import { formatDate } from "@shared/lib/relative-time";
import { Field } from "@shared/ui/Field";
import { FieldHint } from "@shared/ui/FieldHint";
import { Switch } from "@shared/ui/Switch";
import { TextArea, TextInput } from "@shared/ui/TextInput";

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

  return (
    <div className="flex flex-col gap-3">
      <Field label={t("settings.legal.titleLabel")} bright required>
        <TextInput
          value={title}
          maxLength={TITLE_LIMIT}
          disabled={!canSet}
          onChange={(event) => onChange({ ...value, title: event.target.value })}
        />
      </Field>
      <Field label={t("settings.legal.bodyLabel")} bright required hint={t("settings.legal.bodyHint", { limit: TEXT_LIMIT })}>
        <div className="relative">
          <TextArea
            rows={16}
            className="w-full font-mono"
            value={body}
            disabled={!canSet}
            onChange={(event) => onChange({ ...value, body: event.target.value })}
          />
          {/* over the corner, left of the scrollbar; the text scrolls under its backing */}
          <span
            className={`pointer-events-none absolute bottom-4 right-4 rounded-full bg-input px-1.5 py-0.5 text-[11px] tabular-nums ${
              length > TEXT_LIMIT ? "text-error" : "text-muted-foreground"
            }`}
          >
            {length} / {TEXT_LIMIT}
          </span>
        </div>
      </Field>
      {canSet && canReaccept && (
        <div className="flex items-center gap-3">
          <p className="flex min-w-0 flex-1 items-center gap-1.5 text-sm font-medium text-foreground">
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
