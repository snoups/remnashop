import { Layers, Link2, MonitorSmartphone, Share2, ShoppingBag, Smartphone } from "lucide-react";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getShopSettings, updateShopSettings } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseOptionalInt, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Field } from "@shared/ui/Field";
import { SuffixInput, TextInput } from "@shared/ui/TextInput";
import { SETTINGS_ROWS_CLASS, SETTINGS_SECTION_CLASS } from "@shared/ui/classes";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SettingsRow } from "@shared/ui/SettingsRow";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

export function ShopSettingsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("SHOP_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getShopSettings);
  const [maxActiveSubscriptions, setMaxActiveSubscriptions] = useState("");
  const [deviceSingleResetEnabled, setDeviceSingleResetEnabled] = useState(true);
  const [deviceSingleResetCooldownHours, setDeviceSingleResetCooldownHours] = useState("0");
  const [deviceAllResetEnabled, setDeviceAllResetEnabled] = useState(true);
  const [deviceAllResetCooldownHours, setDeviceAllResetCooldownHours] = useState("0");
  const [linkResetEnabled, setLinkResetEnabled] = useState(true);
  const [linkResetCooldownHours, setLinkResetCooldownHours] = useState("0");
  const [referralResetEnabled, setReferralResetEnabled] = useState(true);
  const [referralResetCooldownHours, setReferralResetCooldownHours] = useState("0");
  const [supportTelegram, setSupportTelegram] = useState("");
  const [supportUrl, setSupportUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (state.kind !== "ready") return;
    setMaxActiveSubscriptions(
      state.data.max_active_subscriptions === null ? "" : String(state.data.max_active_subscriptions),
    );
    setDeviceSingleResetEnabled(state.data.device_single_reset_enabled);
    setDeviceSingleResetCooldownHours(String(state.data.device_single_reset_cooldown_hours));
    setDeviceAllResetEnabled(state.data.device_all_reset_enabled);
    setDeviceAllResetCooldownHours(String(state.data.device_all_reset_cooldown_hours));
    setLinkResetEnabled(state.data.link_reset_enabled);
    setLinkResetCooldownHours(String(state.data.link_reset_cooldown_hours));
    setReferralResetEnabled(state.data.referral_reset_enabled);
    setReferralResetCooldownHours(String(state.data.referral_reset_cooldown_hours));
    setSupportTelegram(state.data.support_telegram ?? "");
    setSupportUrl(state.data.support_url ?? "");
  }, [state]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedMax = parseOptionalInt(maxActiveSubscriptions, 1);
    const parsedSingleCooldown = parseRequiredInt(deviceSingleResetCooldownHours, 0);
    const parsedAllCooldown = parseRequiredInt(deviceAllResetCooldownHours, 0);
    const parsedLinkCooldown = parseRequiredInt(linkResetCooldownHours, 0);
    const parsedReferralCooldown = parseRequiredInt(referralResetCooldownHours, 0);
    if (
      parsedMax === undefined ||
      parsedSingleCooldown === undefined ||
      parsedAllCooldown === undefined ||
      parsedLinkCooldown === undefined ||
      parsedReferralCooldown === undefined
    ) {
      toast.error(t("settings.shop.invalidInput"));
      return;
    }

    setIsSubmitting(true);
    try {
      const settings = await updateShopSettings({
        max_active_subscriptions: parsedMax,
        device_single_reset_enabled: deviceSingleResetEnabled,
        device_single_reset_cooldown_hours: parsedSingleCooldown,
        device_all_reset_enabled: deviceAllResetEnabled,
        device_all_reset_cooldown_hours: parsedAllCooldown,
        link_reset_enabled: linkResetEnabled,
        link_reset_cooldown_hours: parsedLinkCooldown,
        referral_reset_enabled: referralResetEnabled,
        referral_reset_cooldown_hours: parsedReferralCooldown,
        // blank clears it; the backend takes "@name" and t.me links as well
        support_telegram: supportTelegram.trim() || null,
        support_url: supportUrl.trim() || null,
      });
      setData(settings);
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const saved = state.kind === "ready" ? state.data : null;
  const dirty =
    saved !== null &&
    (maxActiveSubscriptions !== (saved.max_active_subscriptions === null ? "" : String(saved.max_active_subscriptions)) ||
      deviceSingleResetEnabled !== saved.device_single_reset_enabled ||
      deviceSingleResetCooldownHours !== String(saved.device_single_reset_cooldown_hours) ||
      deviceAllResetEnabled !== saved.device_all_reset_enabled ||
      deviceAllResetCooldownHours !== String(saved.device_all_reset_cooldown_hours) ||
      linkResetEnabled !== saved.link_reset_enabled ||
      linkResetCooldownHours !== String(saved.link_reset_cooldown_hours) ||
      referralResetEnabled !== saved.referral_reset_enabled ||
      referralResetCooldownHours !== String(saved.referral_reset_cooldown_hours) ||
      supportTelegram !== (saved.support_telegram ?? "") ||
      supportUrl !== (saved.support_url ?? ""));

  return (
    <Card>
      <CardHeader
        icon={ShoppingBag}
        title={t("settings.shop.title")}
        description={t("settings.shop.description")}
      />

      {state.kind === "loading" && (
        <Spinner size="card" />
      )}
      {state.kind === "error" && (
        <ErrorState text={t("common.loadError")} />
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
          <div className={SETTINGS_ROWS_CLASS}>
            <SettingsRow icon={Layers} label={t("settings.shop.maxActiveSubscriptionsLabel")}>
              <TextInput
                type="number"
                onKeyDown={blockNonIntegerKeys}
                step="1"
                min="1"
                placeholder={t("settings.shop.unlimitedPlaceholder")}
                value={maxActiveSubscriptions}
                onChange={(event) => setMaxActiveSubscriptions(event.target.value)}
                className="w-24 shrink-0"
              />
              {/* switch-sized gap: this input lines up with the reset rows' hours */}
              <span className="w-10 shrink-0" />
            </SettingsRow>
            <ResetRow
              icon={Smartphone}
              label={t("settings.shop.deviceSingleResetLabel")}
              enabled={deviceSingleResetEnabled}
              onEnabledChange={setDeviceSingleResetEnabled}
              cooldownHours={deviceSingleResetCooldownHours}
              onCooldownChange={setDeviceSingleResetCooldownHours}
            />
            <ResetRow
              icon={MonitorSmartphone}
              label={t("settings.shop.deviceAllResetLabel")}
              enabled={deviceAllResetEnabled}
              onEnabledChange={setDeviceAllResetEnabled}
              cooldownHours={deviceAllResetCooldownHours}
              onCooldownChange={setDeviceAllResetCooldownHours}
            />
            <ResetRow
              icon={Link2}
              label={t("settings.shop.linkResetLabel")}
              enabled={linkResetEnabled}
              onEnabledChange={setLinkResetEnabled}
              cooldownHours={linkResetCooldownHours}
              onCooldownChange={setLinkResetCooldownHours}
            />
            <ResetRow
              icon={Share2}
              label={t("settings.shop.referralResetLabel")}
              enabled={referralResetEnabled}
              onEnabledChange={setReferralResetEnabled}
              cooldownHours={referralResetCooldownHours}
              onCooldownChange={setReferralResetCooldownHours}
            />
          </div>

          {/* where the cabinet's "Support" leads: either or both */}
          <div className={SETTINGS_SECTION_CLASS}>
            <div className="flex flex-col gap-3 px-[12.5px] pb-2 pt-1">
              <Field bright label={t("settings.shop.supportTelegramLabel")}>
                <TextInput
                  placeholder={t("settings.shop.supportTelegramPlaceholder")}
                  value={supportTelegram}
                  onChange={(event) => setSupportTelegram(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field bright label={t("settings.shop.supportUrlLabel")}>
                <TextInput
                  placeholder={t("settings.shop.supportUrlPlaceholder")}
                  value={supportUrl}
                  onChange={(event) => setSupportUrl(event.target.value)}
                  autoComplete="off"
                />
              </Field>
            </div>
          </div>
          </fieldset>

          {canManage && <SaveFooter dirty={dirty} saving={isSubmitting} />}
        </form>
      )}
    </Card>
  );
}

interface ResetRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  cooldownHours: string;
  onCooldownChange: (value: string) => void;
}

function ResetRow({
  icon,
  label,
  enabled,
  onEnabledChange,
  cooldownHours,
  onCooldownChange,
}: ResetRowProps) {
  const { t } = useTranslation();
  return (
    <SettingsRow icon={icon} label={label}>
      <SuffixInput
        type="number"
        onKeyDown={blockNonIntegerKeys}
        step="1"
        min="0"
        suffix={t("settings.shop.hoursSuffix")}
        value={cooldownHours}
        onChange={(event) => onCooldownChange(event.target.value)}
        disabled={!enabled}
        className="w-24 shrink-0"
      />
      <Switch checked={enabled} onChange={onEnabledChange} />
    </SettingsRow>
  );
}
