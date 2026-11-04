import type { ParseKeys } from "i18next";
import {
  Bell,
  BellRing,
  CalendarX,
  CircleAlert,
  Send,
  Server,
  ShieldAlert,
  ShoppingCart,
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
import { useLoadGateHold } from "@shared/lib/load-gate";
import { currentPushEndpoint, detectPushSupport, disablePush, enablePush } from "@shared/lib/push";
import type { EnablePushResult } from "@shared/lib/push";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { Spinner } from "@shared/ui/Spinner";
import { PushDevicesList } from "@features/notification-settings/PushDevicesList";

// Mirrors NOTIFICATION_GROUPS (backend/app/modules/notifications/dto.py); an
// unknown group from the server still renders, just with the fallback icon.
const GROUP_ICONS: Record<string, LucideIcon> = {
  security: ShieldAlert,
  failures: CircleAlert,
  money: ShoppingCart,
  infrastructure: Server,
  customers: Users,
  subscriptions: CalendarX,
};

const PUSH_ERRORS: Record<Exclude<EnablePushResult, "subscribed">, ParseKeys> = {
  denied: "profile.notifications.push.denied",
  "not-configured": "profile.notifications.push.notConfiguredError",
  failed: "profile.notifications.push.failed",
};

export function NotificationChannelsForm() {
  const { t } = useTranslation();
  const canView = usePermissions().includes("NOTIFICATIONS_VIEW");
  const [state, , setData] = useAsyncResource(getNotificationChannels);
  // one save at a time: each sends the whole matrix, so overlapping answers could land out of order
  const [isSaving, setIsSaving] = useState(false);
  // null until the browser says: the switch shouldn't flip on in front of the user
  const [pushOn, setPushOn] = useState<boolean | null>(null);
  const [isTogglingPush, setIsTogglingPush] = useState(false);
  const [devicesVersion, setDevicesVersion] = useState(0);
  const support = detectPushSupport();
  useLoadGateHold(pushOn === null);

  useEffect(() => {
    currentPushEndpoint().then(
      (endpoint) => setPushOn(endpoint !== null),
      () => setPushOn(false),
    );
  }, []);

  if (!canView) return null;

  const toggle = async (current: NotificationChannels, group: string, channel: string) => {
    // dropped rather than disabled: greying every switch for each save would flicker
    if (isSaving) return;
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

  // the bot's column only once Telegram is linked: until then it has nowhere to send
  const shownChannels = (data: NotificationChannels) =>
    data.available_channels.filter((channel) => channel !== "telegram" || data.telegram_available);

  return (
    <Section
      icon={Bell}
      title={t("profile.notifications.title")}
      description={t(
        state.kind === "ready" && !state.data.telegram_available
          ? "profile.notifications.descriptionPushOnly"
          : "profile.notifications.description",
      )}
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <>
          <SectionRows>
            <Row icon={BellRing} label={t("profile.notifications.push.label")} description={pushStatus(state.data)}>
              {pushStatus(state.data) === null && (
                <>
                  {pushOn && (
                    <Button variant="glass" size="sm" icon={Send} onClick={() => void test()}>
                      {t("profile.notifications.push.test")}
                    </Button>
                  )}
                  <Switch checked={pushOn ?? false} onChange={(on) => void togglePush(on)} disabled={isTogglingPush} />
                </>
              )}
            </Row>
            {state.data.telegram_available && (
              <Row
                icon={Send}
                label={t("profile.notifications.telegram.label")}
                description={t("profile.oauthAccounts.connected")}
              />
            )}
          </SectionRows>

          {/* SectionRows divided's line and spacing, the column heads outside the rows so no line follows them */}
          <div className="mt-2 border-t border-white/[0.08] pt-2">
            {/* over the rows' switches: 48px each, 8px apart, 16px from the edge as in a Row; -mb-3 pulls the
                first row's switches up close under the heads */}
            <div className={`-mb-3 flex justify-end gap-2 pr-4 ${EYEBROW_CLASS}`}>
              {shownChannels(state.data).map((channel) => (
                <span key={channel} className="flex w-12 justify-center whitespace-nowrap">
                  {t(`profile.notifications.channels.${channel}` as ParseKeys)}
                </span>
              ))}
            </div>
            <SectionRows flush>
              {state.data.available_groups.map((group) => {
                const chosen = state.data.channels[group] ?? [];
                return (
                  <Row
                    key={group}
                    icon={GROUP_ICONS[group] ?? Bell}
                    label={t(`profile.notifications.groups.${group}.title` as ParseKeys)}
                    description={t(`profile.notifications.groups.${group}.description` as ParseKeys)}
                  >
                    {shownChannels(state.data).map((channel) => (
                      // an unavailable channel delivers nothing, so it reads off whatever is stored
                      <Switch
                        key={channel}
                        checked={isChannelAvailable(state.data, channel) && chosen.includes(channel)}
                        disabled={!isChannelAvailable(state.data, channel)}
                        onChange={() => void toggle(state.data, group, channel)}
                      />
                    ))}
                  </Row>
                );
              })}
            </SectionRows>
          </div>

          {state.data.is_push_configured && support === "ready" && (
            <PushDevicesList
              version={devicesVersion}
              onRemoved={(endpoint) => {
                // disablePush unsubscribes the browser even when the server call fails
                void currentPushEndpoint()
                  .then((own) =>
                    own === endpoint
                      ? disablePush(pushApi, { optOut: true }).finally(() => setPushOn(false))
                      : undefined,
                  )
                  .catch(() => undefined);
              }}
            />
          )}
        </>
      )}
    </Section>
  );
}
