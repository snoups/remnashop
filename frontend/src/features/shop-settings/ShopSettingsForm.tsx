import { Layers, Link2, MonitorSmartphone, Share2, ShoppingBag, Smartphone } from "lucide-react";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getShopSettings, updateShopSettings } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseOptionalInt, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { TextWidth } from "@shared/ui/glass/TextWidth";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

type FieldName = "max" | "deviceSingle" | "deviceAll" | "link" | "referral";

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
  }, [state]);

  const validation = useFieldValidation<FieldName>();
  const hoursError = (value: string) =>
    value.trim() === ""
      ? t("errors.validation.required")
      : parseRequiredInt(value, 0) === undefined
        ? t("errors.validation.min", { min: 0 })
        : null;
  const errors: Record<FieldName, string | null> = {
    max:
      parseOptionalInt(maxActiveSubscriptions, 1) === undefined ? t("errors.validation.min", { min: 1 }) : null,
    deviceSingle: hoursError(deviceSingleResetCooldownHours),
    deviceAll: hoursError(deviceAllResetCooldownHours),
    link: hoursError(linkResetCooldownHours),
    referral: hoursError(referralResetCooldownHours),
  };
  const shown = (name: FieldName) => validation.visible(name, errors[name]);
  // what an input takes to report its value and its error state
  const watch = (name: FieldName) => ({
    onBlur: validation.touch(name),
    "aria-invalid": shown(name) !== undefined,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    validation.submit();
    if (Object.values(errors).some((error) => error !== null)) return;

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
      });
      setData(settings);
      validation.reset();
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
      referralResetCooldownHours !== String(saved.referral_reset_cooldown_hours));

  const unlimited = t("settings.shop.unlimitedPlaceholder");
  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={ShoppingBag}
        title={t("settings.shop.title")}
        description={t("settings.shop.description")}
        footer={state.kind === "ready" && canManage && <SaveFooter variant="glassAccent" dirty={dirty} saving={isSubmitting} />}
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <fieldset disabled={!canManage} className="contents">
            <SectionRows>
              <Row
                icon={Layers}
                label={t("settings.shop.maxActiveSubscriptionsLabel")}
                description={shown("max") && <span className="text-error">{shown("max")}</span>}
              >
                {/* 2px: the reset rows end 16px in (switch), this one 14px */}
                <TextWidth text={unlimited} className="mr-0.5">
                  <Input
                    size="sm"
                    className="flex-1"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    step="1"
                    min="1"
                    placeholder={unlimited}
                    value={maxActiveSubscriptions}
                    onChange={(event) => setMaxActiveSubscriptions(event.target.value)}
                    {...watch("max")}
                  />
                </TextWidth>
              </Row>
              <ResetRow
                icon={Smartphone}
                label={t("settings.shop.deviceSingleResetLabel")}
                width={unlimited}
                error={shown("deviceSingle")}
                inputProps={watch("deviceSingle")}
                enabled={deviceSingleResetEnabled}
                onEnabledChange={setDeviceSingleResetEnabled}
                cooldownHours={deviceSingleResetCooldownHours}
                onCooldownChange={setDeviceSingleResetCooldownHours}
              />
              <ResetRow
                icon={MonitorSmartphone}
                label={t("settings.shop.deviceAllResetLabel")}
                width={unlimited}
                error={shown("deviceAll")}
                inputProps={watch("deviceAll")}
                enabled={deviceAllResetEnabled}
                onEnabledChange={setDeviceAllResetEnabled}
                cooldownHours={deviceAllResetCooldownHours}
                onCooldownChange={setDeviceAllResetCooldownHours}
              />
              <ResetRow
                icon={Link2}
                label={t("settings.shop.linkResetLabel")}
                width={unlimited}
                error={shown("link")}
                inputProps={watch("link")}
                enabled={linkResetEnabled}
                onEnabledChange={setLinkResetEnabled}
                cooldownHours={linkResetCooldownHours}
                onCooldownChange={setLinkResetCooldownHours}
              />
              <ResetRow
                icon={Share2}
                label={t("settings.shop.referralResetLabel")}
                width={unlimited}
                error={shown("referral")}
                inputProps={watch("referral")}
                enabled={referralResetEnabled}
                onEnabledChange={setReferralResetEnabled}
                cooldownHours={referralResetCooldownHours}
                onCooldownChange={setReferralResetCooldownHours}
              />
            </SectionRows>
          </fieldset>
        )}
      </Section>
    </form>
  );
}

interface ResetRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  /** the text the limit field above is sized to: hours + switch take its width */
  width: string;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  cooldownHours: string;
  onCooldownChange: (value: string) => void;
  /** shown in red under the label */
  error?: string;
  inputProps: { onBlur: () => void; "aria-invalid": boolean };
}

function ResetRow({
  icon,
  label,
  width,
  enabled,
  onEnabledChange,
  cooldownHours,
  onCooldownChange,
  error,
  inputProps,
}: ResetRowProps) {
  const { t } = useTranslation();
  return (
    <Row icon={icon} label={label} description={error && <span className="text-error">{error}</span>}>
      <TextWidth text={width}>
        <Input
          size="sm"
          className="flex-1"
          type="number"
          onKeyDown={blockNonIntegerKeys}
          step="1"
          min="0"
          suffix={t("settings.shop.hoursSuffix")}
          value={cooldownHours}
          onChange={(event) => onCooldownChange(event.target.value)}
          {...inputProps}
          disabled={!enabled}
        />
        <Switch checked={enabled} onChange={onEnabledChange} />
      </TextWidth>
    </Row>
  );
}
