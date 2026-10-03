import { Bell, CircleAlert, HandCoins, ShieldAlert, ShoppingCart, UserCog, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getNotificationGroups,
  updateNotificationGroups,
  type NotificationGroups,
} from "@entities/event-log/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Card } from "@shared/ui/Card";

// Mirrors NOTIFICATION_GROUPS (backend/app/modules/event_log/dto.py); an
// unknown group from the server still renders, just with the fallback icon.
const GROUP_ICONS: Record<string, LucideIcon> = {
  security: ShieldAlert,
  failures: CircleAlert,
  requests: HandCoins,
  money: ShoppingCart,
  admins: UserCog,
};

export function NotificationSettingsForm() {
  const { t } = useTranslation();
  const canView = usePermissions().includes("NOTIFICATIONS_VIEW");
  const [state, , setData] = useAsyncResource(getNotificationGroups);
  // one save at a time: each sends the whole list, so overlapping answers could land out of order
  const [isSaving, setIsSaving] = useState(false);

  if (!canView) return null;

  const toggle = async (current: NotificationGroups, group: string, enabled: boolean) => {
    const next = enabled ? [...current.groups, group] : current.groups.filter((g) => g !== group);
    setData({ ...current, groups: next });
    setIsSaving(true);
    try {
      setData(await updateNotificationGroups(next));
    } catch (err) {
      setData(current);
      toast.error(getErrorMessage(err, t("profile.notifications.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Bell className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("profile.notifications.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("profile.notifications.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      <div className="mt-4 flex flex-col divide-y divide-border/50">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <p className="text-sm text-error">{t("profile.notifications.loadError")}</p>}
        {state.kind === "ready" &&
          state.data.available.map((group) => {
            const Icon = GROUP_ICONS[group] ?? Bell;
            const enabled = state.data.groups.includes(group);
            return (
              <div key={group} className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground">
                    {t(`profile.notifications.groups.${group}.title`)}
                  </p>
                  <p className="text-[12px] text-muted-foreground">
                    {t(`profile.notifications.groups.${group}.description`)}
                  </p>
                </div>
                <div className="mr-1 flex">
                  <Switch
                    checked={enabled}
                    onChange={(value) => void toggle(state.data, group, value)}
                    disabled={isSaving}
                  />
                </div>
              </div>
            );
          })}
      </div>
    </Card>
  );
}
