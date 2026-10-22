import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  removeLegalText,
  setLegalText,
  type LegalChannel,
  type LegalKind,
  type LegalText,
} from "@entities/legal/api";
import { getErrorMessage } from "@shared/api/http";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/Field";
import { Switch } from "@shared/ui/Switch";
import { Tag } from "@shared/ui/Tag";
import { TextArea, TextInput } from "@shared/ui/TextInput";

const MESSAGE_LIMIT = 32768;
const TITLE_LIMIT = 160;
// the offer is accepted by paying, so only these can ask for it again
const REACCEPTABLE: readonly LegalKind[] = ["USER_AGREEMENT", "PRIVACY_POLICY"];

interface Props {
  kind: LegalKind;
  locale: string;
  channel: LegalChannel | null;
  current: LegalText | undefined;
  hasOverride: boolean;
  fallback: LegalText | undefined;
  canSet: boolean;
  canRemove: boolean;
  onChanged: () => void;
}

export function LegalTextEditor({
  kind,
  locale,
  channel,
  current,
  hasOverride,
  fallback,
  canSet,
  canRemove,
  onChanged,
}: Props) {
  const { t, i18n } = useTranslation();
  const [reaccept, setReaccept] = useState(false);
  const [custom, setCustom] = useState(channel === null || hasOverride);
  const [title, setTitle] = useState(hasOverride || channel === null ? (current?.title ?? "") : (fallback?.title ?? ""));
  const [body, setBody] = useState(hasOverride || channel === null ? (current?.body ?? "") : (fallback?.body ?? ""));
  const [busy, setBusy] = useState(false);

  const length = [...`# ${title}\n\n${body}`].length;
  const tooLong = length > MESSAGE_LIMIT;
  const canEdit = custom && canSet;

  const run = async (action: () => Promise<unknown>, success: boolean) => {
    setBusy(true);
    try {
      await action();
      if (success) toast.success(t("common.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setBusy(false);
    }
  };

  const toggleCustom = (next: boolean) => {
    if (next) {
      setCustom(true);
      return;
    }
    if (!hasOverride) {
      setCustom(false);
      return;
    }
    void run(() => removeLegalText(kind, locale, channel), false);
  };

  return (
    <div className="flex flex-col gap-3">
      {channel !== null && (
        <div className="flex items-center gap-3 px-1">
          <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">{t("settings.legal.ownText")}</p>
          <Switch checked={custom} onChange={toggleCustom} disabled={busy || (hasOverride ? !canRemove : !canSet)} />
        </div>
      )}
      {channel !== null && !custom && (
        <p className="px-1 text-[12.5px] text-muted-foreground">{t("settings.legal.usesCommon")}</p>
      )}
      {custom && (
        <>
          <Field label={t("settings.legal.titleLabel")} required>
            <TextInput
              value={title}
              maxLength={TITLE_LIMIT}
              disabled={!canEdit}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <Field
            label={t("settings.legal.bodyLabel")}
            required
            hint={t("settings.legal.bodyHint")}
            aside={
              <Tag className={tooLong ? "text-error" : ""}>
                {length} / {MESSAGE_LIMIT}
              </Tag>
            }
          >
            <TextArea
              rows={14}
              className="font-mono"
              value={body}
              disabled={!canEdit}
              onChange={(event) => setBody(event.target.value)}
            />
          </Field>
          {canSet && REACCEPTABLE.includes(kind) && (
            <div className="flex flex-col gap-1 px-1">
              <div className="flex items-center gap-3">
                <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">{t("settings.legal.reaccept")}</p>
                <Switch checked={reaccept} onChange={setReaccept} disabled={busy} />
              </div>
              <p className="text-[12px] text-muted-foreground">{t("settings.legal.reacceptHint")}</p>
            </div>
          )}
          {canSet && (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="accent"
                className="w-fit"
                disabled={busy || tooLong || !title.trim() || !body.trim()}
                onClick={() =>
                  void run(
                    () => setLegalText(kind, locale, channel, { title, body, requires_reacceptance: reaccept }),
                    true,
                  )
                }
              >
                {busy ? t("common.saving") : t("common.save")}
              </Button>
              {current?.last_reacceptance_at && (
                <span className="text-[12px] text-muted-foreground">
                  {t("settings.legal.lastReaccept", { date: formatDate(current.last_reacceptance_at, i18n.language) })}
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
