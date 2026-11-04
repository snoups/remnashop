import { Laptop, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { deletePushSubscription, listPushSubscriptions } from "@entities/notifications/api";
import type { PushSubscriptionItem } from "@entities/notifications/api";
import { getErrorMessage } from "@shared/api/http";
import { currentPushEndpoint } from "@shared/lib/push";
import { formatRelative } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { IconButton } from "@shared/ui/IconButton";
import { Row } from "@shared/ui/glass/Row";
import { SectionRows } from "@shared/ui/glass/Section";
import { Tag } from "@shared/ui/Tag";

interface PushDevicesListProps {
  /** bumped by the parent after it subscribes or unsubscribes this browser */
  version: number;
  onRemoved: (endpoint: string) => void;
}

export function PushDevicesList({ version, onRemoved }: PushDevicesListProps) {
  const { t, i18n } = useTranslation();
  // one load for both, so the gate holds until the list and its "this device" mark are in
  const [state, , setData] = useAsyncResource(
    async (signal) => {
      const [result, endpoint] = await Promise.all([listPushSubscriptions(signal), currentPushEndpoint()]);
      return { items: result.items, thisEndpoint: endpoint };
    },
    { deps: [version], keepData: true },
  );
  const items = state.kind === "ready" ? state.data.items : [];
  const thisEndpoint = state.kind === "ready" ? state.data.thisEndpoint : null;

  const remove = async (item: PushSubscriptionItem) => {
    try {
      await deletePushSubscription(item.id);
      setData((current) => ({ ...current, items: current.items.filter((other) => other.id !== item.id) }));
      toast.success(t("profile.notifications.devices.removed"));
      onRemoved(item.endpoint);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <SectionRows divided>
      {state.kind === "ready" && items.length === 0 && (
        <Row icon={Laptop} label={t("profile.notifications.devices.title")} description={t("profile.notifications.devices.empty")} />
      )}
        {items.map((item) => (
          <Row
            key={item.id}
            icon={Laptop}
            label={<span className="min-w-0 truncate">{item.user_agent ?? t("common.none")}</span>}
            description={t("profile.notifications.devices.lastActive", {
              time: formatRelative(item.last_seen_at, i18n.language),
            })}
          >
            {item.endpoint === thisEndpoint && <Tag>{t("profile.notifications.devices.thisDevice")}</Tag>}
            <IconButton size="8" tone="danger" onClick={() => void remove(item)}>
              <Trash2 className="size-4" />
            </IconButton>
          </Row>
        ))}
    </SectionRows>
  );
}
