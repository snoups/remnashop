import { Laptop, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { deletePushSubscription, listPushSubscriptions } from "@entities/notifications/api";
import type { PushSubscriptionItem } from "@entities/notifications/api";
import { getErrorMessage } from "@shared/api/http";
import { currentPushEndpoint } from "@shared/lib/push";
import { formatRelative } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { IconButton } from "@shared/ui/IconButton";
import { Tag } from "@shared/ui/Tag";

interface PushDevicesListProps {
  /** bumped by the parent after it subscribes or unsubscribes this browser */
  version: number;
  onRemoved: (endpoint: string) => void;
}

export function PushDevicesList({ version, onRemoved }: PushDevicesListProps) {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<PushSubscriptionItem[]>([]);
  const [thisEndpoint, setThisEndpoint] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listPushSubscriptions(controller.signal).then(
      (result) => setItems(result.items),
      () => undefined,
    );
    void currentPushEndpoint().then(setThisEndpoint);
    return () => controller.abort();
  }, [version]);

  const remove = async (item: PushSubscriptionItem) => {
    try {
      await deletePushSubscription(item.id);
      setItems((current) => current.filter((other) => other.id !== item.id));
      toast.success(t("profile.notifications.devices.removed"));
      onRemoved(item.endpoint);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <div className="flex flex-col">
      <p className="px-2.5 pb-1 text-[12px] font-medium text-muted-foreground">
        {t("profile.notifications.devices.title")}
      </p>
      {items.length === 0 && (
        <p className="px-2.5 py-2 text-[12.5px] text-muted-foreground">{t("profile.notifications.devices.empty")}</p>
      )}
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-3 rounded-full px-2.5 py-2 hover:bg-white/[0.04]">
          <Laptop className="size-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-foreground">{item.user_agent ?? t("common.none")}</p>
            <p className="text-[12px] text-muted-foreground">
              {t("profile.notifications.devices.lastActive", { time: formatRelative(item.last_seen_at, i18n.language) })}
            </p>
          </div>
          {item.endpoint === thisEndpoint && <Tag>{t("profile.notifications.devices.thisDevice")}</Tag>}
          <IconButton size="8" tone="danger" onClick={() => void remove(item)}>
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      ))}
    </div>
  );
}
