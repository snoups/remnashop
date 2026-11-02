import { useId } from "react";
import { useTranslation } from "react-i18next";

import { TEXT_LIMIT, TITLE_LIMIT, textLength, type TextDraft } from "@features/legal-documents-editor/legal-drafts";
import { formatDate } from "@shared/lib/relative-time";
import { FieldHint } from "@shared/ui/FieldHint";
import { Field } from "@shared/ui/glass/Field";
import { Input, TextArea } from "@shared/ui/glass/Input";
import { Switch } from "@shared/ui/glass/Switch";

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
        <TextArea
          id={`${id}-body`}
          rows={16}
          mono
          value={body}
          disabled={!canSet}
          onChange={(event) => onChange({ ...value, body: event.target.value })}
          corner={
            <span className={length > TEXT_LIMIT ? "text-error" : undefined}>
              {length} / {TEXT_LIMIT}
            </span>
          }
        />
      </Field>
      {canSet && canReaccept && (
        <div className="flex items-center gap-3">
          <p className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] font-medium text-foreground">
            {t("settings.legal.reaccept")}
            <FieldHint text={t("settings.legal.reacceptHint")} glass />
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
