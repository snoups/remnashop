import { Layers, Link2, MonitorSmartphone, ShoppingBag, Smartphone } from "lucide-react";
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
import { Button } from "@shared/ui/Button";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";


const rowIconClassName =
  "flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground";

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
  }, [state]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedMax = parseOptionalInt(maxActiveSubscriptions, 1);
    const parsedSingleCooldown = parseRequiredInt(deviceSingleResetCooldownHours, 0);
    const parsedAllCooldown = parseRequiredInt(deviceAllResetCooldownHours, 0);
    const parsedLinkCooldown = parseRequiredInt(linkResetCooldownHours, 0);
    if (
      parsedMax === undefined ||
      parsedSingleCooldown === undefined ||
      parsedAllCooldown === undefined ||
      parsedLinkCooldown === undefined
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
      });
      setData(settings);
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

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
        <ErrorState text={t("settings.shop.loadError")} />
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
          <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
            <div className={rowIconClassName}>
              <Layers className="size-4" />
            </div>
            <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
              {t("settings.shop.maxActiveSubscriptionsLabel")}
            </p>
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
            {/* switch-sized gap, so this input lines up with the reset rows' inputs */}
            <span className="mr-1 w-10 shrink-0" />
          </div>

          <div className="mt-2 flex flex-col gap-1 border-t border-white/[0.08] pt-2">
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
          </div>
          </fieldset>

          {canManage && (
            <Button
              variant="accent"
              className="mt-4 w-fit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )}
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
  icon: Icon,
  label,
  enabled,
  onEnabledChange,
  cooldownHours,
  onCooldownChange,
}: ResetRowProps) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
      <div className={rowIconClassName}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        <p className="text-[12px] text-muted-foreground">{t("settings.shop.cooldownHoursLabel")}</p>
      </div>
      <TextInput
        type="number"
        onKeyDown={blockNonIntegerKeys}
        step="1"
        min="0"
        value={cooldownHours}
        onChange={(event) => onCooldownChange(event.target.value)}
        disabled={!enabled}
        className="w-24 shrink-0"
      />
      <div className="mr-1 flex">
        <Switch checked={enabled} onChange={onEnabledChange} />
      </div>
    </div>
  );
}
