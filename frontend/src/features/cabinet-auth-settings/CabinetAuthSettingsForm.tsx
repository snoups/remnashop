import { DoorOpen, Globe, Mail } from "lucide-react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import {
  getCabinetAuthSettings,
  updateCabinetAuthSettings,
  type CabinetAuthSettings,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { TelegramIcon } from "@shared/ui/BrandIcons";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type MethodKey = keyof CabinetAuthSettings;

const METHODS: { key: MethodKey; label: "telegram" | "google" | "yandex" | "email"; icon: ComponentType<{ className?: string }>; path?: string }[] = [
  { key: "telegram_enabled", label: "telegram", icon: TelegramIcon },
  { key: "google_enabled", label: "google", icon: Globe, path: "/login/callback/google" },
  { key: "yandex_enabled", label: "yandex", icon: Globe, path: "/login/callback/yandex" },
  { key: "email_enabled", label: "email", icon: Mail },
];

export function CabinetAuthSettingsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("CABINET_AUTH_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getCabinetAuthSettings);
  const [pendingKey, setPendingKey] = useState<MethodKey | null>(null);

  const handleToggle = async (key: MethodKey, next: boolean) => {
    setPendingKey(key);
    try {
      setData(await updateCabinetAuthSettings({ [key]: next }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setPendingKey(null);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={DoorOpen}
        title={t("settings.cabinetAuth.title")}
        description={t("settings.cabinetAuth.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.cabinetAuth.loadError")} />}
      {state.kind === "ready" && (
        <div className="mt-4 flex flex-col gap-1">
          {METHODS.map(({ key, label, icon: Icon, path }) => (
            <div
              key={key}
              className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                <Icon className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-foreground">
                  {t(`settings.cabinetAuth.methods.${label}`)}
                </p>
                {path && (
                  <p className="text-[12px] text-muted-foreground">
                    {t("settings.oauth.redirectHint", { path })}
                  </p>
                )}
              </div>
              <div className="mr-1 flex">
                <Switch
                  checked={state.data[key]}
                  onChange={(value) => void handleToggle(key, value)}
                  disabled={!canManage || pendingKey !== null}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
