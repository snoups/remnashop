import { Layers, Link2, MonitorSmartphone, ShoppingBag, Smartphone } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getShopSettings, updateShopSettings } from "@entities/settings/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseOptionalInt, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

const inputClassName =
  "w-24 shrink-0 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50";

const rowIconClassName =
  "flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground";

export function ShopSettingsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
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
      toast.success(t("settings.shop.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <ShoppingBag className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.shop.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("settings.shop.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {state.kind === "loading" && (
        <Spinner className="mt-4" />
      )}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("settings.shop.loadError")}</p>
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
            <div className={rowIconClassName}>
              <Layers className="size-4" />
            </div>
            <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
              {t("settings.shop.maxActiveSubscriptionsLabel")}
            </p>
            <input
              type="number"
              step="1"
              min="1"
              placeholder={t("settings.shop.unlimitedPlaceholder")}
              aria-label={t("settings.shop.maxActiveSubscriptionsLabel")}
              value={maxActiveSubscriptions}
              onChange={(event) => setMaxActiveSubscriptions(event.target.value)}
              className={inputClassName}
            />
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

          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="mt-4 w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("settings.shop.saving") : t("settings.shop.save")}
          </motion.button>
        </form>
      )}
    </div>
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
    <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
      <div className={rowIconClassName}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        <p className="text-[12px] text-muted-foreground">{t("settings.shop.cooldownHoursLabel")}</p>
      </div>
      <input
        type="number"
        step="1"
        min="0"
        aria-label={t("settings.shop.cooldownHoursLabel")}
        value={cooldownHours}
        onChange={(event) => onCooldownChange(event.target.value)}
        disabled={!enabled}
        className={inputClassName}
      />
      <Switch checked={enabled} onChange={onEnabledChange} ariaLabel={label} />
    </div>
  );
}
