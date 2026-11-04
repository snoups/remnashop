import { useTranslation } from "react-i18next";

import type { BroadcastDelivery } from "@entities/broadcasts/api";
import { Mail, Megaphone, Send } from "lucide-react";

import { Row } from "@shared/ui/glass/Row";
import { Switch } from "@shared/ui/glass/Switch";
import { PillTabs } from "@shared/ui/PillTabs";

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
    <>
      <Row
        icon={Send}
        label={t("broadcasts.editor.delivery.title")}
        description={t(`broadcasts.editor.delivery.hint.${form.delivery}`)}
      >
        <PillTabs
          items={DELIVERIES.map((delivery) => ({ key: delivery, label: t(`broadcasts.editor.delivery.option.${delivery}`) }))}
          activeKey={form.delivery}
          onSelect={(delivery) => onChange(setDelivery(form, delivery))}
          disabled={disabled}
        />
      </Row>
      {form.delivery === "TELEGRAM" && (
        <Row
          icon={Mail}
          label={t("broadcasts.editor.delivery.fallback.title")}
          description={t("broadcasts.editor.delivery.fallback.hint")}
        >
          <Switch
            checked={form.email_fallback}
            disabled={disabled}
            onChange={(on) => onChange(setEmailFallback(form, on))}
          />
        </Row>
      )}
      {canPostToChannel && (
        <Row
          icon={Megaphone}
          label={
            channelName
              ? t("broadcasts.editor.channel.titleNamed", { name: channelName })
              : t("broadcasts.editor.channel.title")
          }
          description={t("broadcasts.editor.channel.hint")}
        >
          <Switch
            checked={form.post_to_channel}
            disabled={disabled || (channelMissing && !form.post_to_channel)}
            onChange={(post_to_channel) => onChange({ ...form, post_to_channel })}
          />
        </Row>
      )}
    </>
  );
}
