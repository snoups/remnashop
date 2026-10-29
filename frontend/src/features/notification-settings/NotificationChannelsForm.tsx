import type { ParseKeys } from "i18next";
import {
  Bell,
  BellRing,
  CalendarX,
  CircleAlert,
  HandCoins,
  Send,
  Server,
  ShieldAlert,
  ShoppingCart,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getNotificationChannels, sendTestPush, updateNotificationChannels } from "@entities/notifications/api";
import type { NotificationChannels } from "@entities/notifications/api";
import { pushApi } from "@entities/notifications/push-api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currentPushEndpoint, detectPushSupport, disablePush, enablePush } from "@shared/lib/push";
import type { EnablePushResult } from "@shared/lib/push";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { PushDevicesList } from "@features/notification-settings/PushDevicesList";

// Mirrors NOTIFICATION_GROUPS (backend/app/modules/notifications/dto.py); an
// unknown group from the server still renders, just with the fallback icon.
const GROUP_ICONS: Record<string, LucideIcon> = {
  security: ShieldAlert,
  failures: CircleAlert,
  requests: HandCoins,
  money: ShoppingCart,
  admins: UserCog,
  infrastructure: Server,
  customers: Users,
  subscriptions: CalendarX,
};

const PUSH_ERRORS: Record<Exclude<EnablePushResult, "subscribed">, ParseKeys> = {
  denied: "profile.notifications.push.denied",
  "not-configured": "profile.notifications.push.notConfigured",
  failed: "profile.notifications.push.failed",
};

export function NotificationChannelsForm() {
  const { t } = useTranslation();
  const canView = usePermissions().includes("NOTIFICATIONS_VIEW");
  const [state, , setData] = useAsyncResource(getNotificationChannels);
  // one save at a time: each sends the whole matrix, so overlapping answers could land out of order
  const [isSaving, setIsSaving] = useState(false);
  const [pushOn, setPushOn] = useState(false);
  const [isTogglingPush, setIsTogglingPush] = useState(false);
  const [devicesVersion, setDevicesVersion] = useState(0);
  const support = detectPushSupport();

  useEffect(() => {
    void currentPushEndpoint().then((endpoint) => setPushOn(endpoint !== null));
  }, []);

  if (!canView) return null;

  const toggle = async (current: NotificationChannels, group: string, channel: string) => {
    const chosen = current.channels[group] ?? [];
    const next = {
      ...current.channels,
      [group]: chosen.includes(channel) ? chosen.filter((c) => c !== channel) : [...chosen, channel],
    };
    setData({ ...current, channels: next });
    setIsSaving(true);
    try {
      setData(await updateNotificationChannels(next));
    } catch (err) {
      setData(current);
      toast.error(getErrorMessage(err, t("profile.notifications.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  const togglePush = async (on: boolean) => {
    setIsTogglingPush(true);
    try {
      if (on) {
        const result = await enablePush(pushApi);
        if (result !== "subscribed") {
          toast.error(t(PUSH_ERRORS[result]));
          return;
        }
      } else {
        await disablePush(pushApi, { optOut: true });
      }
      setPushOn(on);
      setDevicesVersion((v) => v + 1);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsTogglingPush(false);
    }
  };

  const test = async () => {
    try {
      await sendTestPush();
      toast.success(t("profile.notifications.push.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const pushStatus = (data: NotificationChannels) => {
    if (!data.is_push_configured) return t("profile.notifications.push.notConfigured");
    if (support === "ios-needs-install") return t("profile.notifications.push.iosInstall");
    if (support === "unsupported") return t("profile.notifications.push.unsupported");
    return null;
  };

  const isChannelAvailable = (data: NotificationChannels, channel: string) =>
    channel === "push" ? data.is_push_configured : channel === "telegram" ? data.telegram_available : true;

  return (
    <Card>
      <CardHeader
        icon={Bell}
        title={t("profile.notifications.title")}
        description={t("profile.notifications.description")}
      />

      <div className="mt-4 flex flex-col gap-3">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <>
            <div className="flex flex-col gap-2 rounded-2xl border border-border/60 p-3">
              <div className="flex flex-wrap items-center gap-3">
                <BellRing className="size-4 text-muted-foreground" />
                <span className="flex-1 text-[13px] font-medium text-foreground">
                  {t("profile.notifications.push.label")}
                </span>
                {pushStatus(state.data) ?? (
                  <>
                    {pushOn && (
                      <Button variant="secondary" size="sm" onClick={() => void test()}>
                        <Send className="size-3.5" />
                        {t("profile.notifications.push.test")}
                      </Button>
                    )}
                    <Switch checked={pushOn} onChange={(on) => void togglePush(on)} disabled={isTogglingPush} />
                  </>
                )}
              </div>
              <div className="flex items-center gap-3">
                <Send className="size-4 text-muted-foreground" />
                <span className="flex-1 text-[13px] font-medium text-foreground">
                  {t("profile.notifications.telegram.label")}
                </span>
                <span className="text-[12px] text-muted-foreground">
                  {t(
                    state.data.telegram_available
                      ? "profile.notifications.telegram.linked"
                      : "profile.notifications.telegram.link",
                  )}
                </span>
              </div>
            </div>

            <div className="flex flex-col divide-y divide-border/50">
              {state.data.available_groups.map((group) => {
                const Icon = GROUP_ICONS[group] ?? Bell;
                const chosen = state.data.channels[group] ?? [];
                return (
                  <div key={group} className="flex flex-wrap items-center gap-3 px-[12.5px] py-2.5">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                      <Icon className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-foreground">
                        {t(`profile.notifications.groups.${group}.title` as ParseKeys)}
                      </p>
                      <p className="text-[12px] text-muted-foreground">
                        {t(`profile.notifications.groups.${group}.description` as ParseKeys)}
                      </p>
                    </div>
                    <div className="flex gap-1.5">
                      {state.data.available_channels.map((channel) => (
                        <ChoiceChip
                          key={channel}
                          size="sm"
                          active={chosen.includes(channel)}
                          disabled={isSaving || !isChannelAvailable(state.data, channel)}
                          onClick={() => void toggle(state.data, group, channel)}
                        >
                          {t(`profile.notifications.channels.${channel}` as ParseKeys)}
                        </ChoiceChip>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {state.data.is_push_configured && support === "ready" && (
              <PushDevicesList
                version={devicesVersion}
                onRemoved={(endpoint) => {
                  // disablePush unsubscribes the browser even when the server call fails
                  void currentPushEndpoint()
                    .then((own) =>
                      own === endpoint ? disablePush(pushApi, { optOut: true }).finally(() => setPushOn(false)) : undefined,
                    )
                    .catch(() => undefined);
                }}
              />
            )}
          </>
        )}
      </div>
    </Card>
  );
}
