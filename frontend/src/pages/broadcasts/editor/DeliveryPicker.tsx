import { useTranslation } from "react-i18next";

import type { BroadcastDelivery } from "@entities/broadcasts/api";
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { Field } from "@shared/ui/Field";
import { Switch } from "@shared/ui/Switch";

import { setDelivery, setEmailFallback } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";

const DELIVERIES: BroadcastDelivery[] = ["TELEGRAM", "EMAIL", "ALL"];

interface DeliveryPickerProps {
  form: EditorForm;
  onChange: (form: EditorForm) => void;
  channelName: string | null;
  channelMissing: boolean;
  disabled: boolean;
}

export function DeliveryPicker({ form, onChange, channelName, channelMissing, disabled }: DeliveryPickerProps) {
  const { t } = useTranslation();
  const canPostToChannel = form.delivery !== "EMAIL";
  return (
    <Card className="flex flex-col gap-3.5">
      <Field label={t("broadcasts.editor.delivery.title")} hint={t(`broadcasts.editor.delivery.hint.${form.delivery}`)}>
        <div className="flex flex-wrap gap-1.5">
          {DELIVERIES.map((delivery) => (
            <ChoiceChip
              key={delivery}
              active={form.delivery === delivery}
              disabled={disabled}
              onClick={() => onChange(setDelivery(form, delivery))}
            >
              {t(`broadcasts.editor.delivery.option.${delivery}`)}
            </ChoiceChip>
          ))}
        </div>
      </Field>
      {form.delivery === "TELEGRAM" && (
        <div className="flex items-center gap-2.5 border-t border-border pt-2.5">
          <Switch
            checked={form.email_fallback}
            disabled={disabled}
            onChange={(on) => onChange(setEmailFallback(form, on))}
          />
          <span className="flex flex-col gap-0.5">
            <span className="text-[13px] font-semibold text-foreground">
              {t("broadcasts.editor.delivery.fallback.title")}
            </span>
            <span className="text-[12px] text-muted-foreground">{t("broadcasts.editor.delivery.fallback.hint")}</span>
          </span>
        </div>
      )}
      {canPostToChannel && (
        <div className="flex items-center gap-2.5 border-t border-border pt-2.5">
          <Switch
            checked={form.post_to_channel}
            disabled={disabled || (channelMissing && !form.post_to_channel)}
            onChange={(post_to_channel) => onChange({ ...form, post_to_channel })}
          />
          <span className="flex flex-col gap-0.5">
            <span className="text-[13px] font-semibold text-foreground">
              {channelName
                ? t("broadcasts.editor.channel.titleNamed", { name: channelName })
                : t("broadcasts.editor.channel.title")}
            </span>
            <span className="text-[12px] text-muted-foreground">
              {t(channelMissing ? "broadcasts.editor.channel.missing" : "broadcasts.editor.channel.hint")}
            </span>
          </span>
        </div>
      )}
    </Card>
  );
}
