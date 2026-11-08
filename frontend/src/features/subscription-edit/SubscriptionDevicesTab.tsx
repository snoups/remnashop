import { Smartphone, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  deleteSubscriptionDevice,
  listSubscriptionDevices,
} from "@entities/subscriptions/api";
import { useAccountPermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { IconButton } from "@shared/ui/IconButton";
import { Spinner } from "@shared/ui/Spinner";

export function SubscriptionDevicesTab({ subscriptionId, userId }: { subscriptionId: number; userId: number }) {
  const { t, i18n } = useTranslation();
  const permissions = useAccountPermissions(userId);
  const canDelete = permissions.includes("SUBSCRIPTIONS_DEVICES_DELETE");
  const [state, reload, setData] = useAsyncResource((signal) => listSubscriptionDevices(subscriptionId, signal));
  const [isBusy, setIsBusy] = useState(false);

  const run = async (action: () => Promise<void>, done: string) => {
    setIsBusy(true);
    try {
      await action();
      toast.success(done);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.devices.error")));
    } finally {
      setIsBusy(false);
    }
  };

  // the row goes at once, so it can't be clicked again while the list reloads
  const deleteDevice = async (hwid: string) => {
    await deleteSubscriptionDevice(subscriptionId, hwid);
    setData((prev) => ({
      items: prev.items.filter((device) => device.hwid !== hwid),
      total: prev.total - 1,
    }));
  };

  return (
    <div className="flex flex-col gap-3">
      <DialogCard>
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && state.data.items.length === 0 && (
          <EmptyState icon={Smartphone} text={t("subscriptions.devices.empty")} />
        )}
        {state.kind === "ready" &&
          state.data.items.map((device) => (
            <Row
              key={device.hwid}
              size="sm"
              icon={Smartphone}
              label={[device.device_model, device.platform].filter(Boolean).join(" · ") || t("common.none")}
              description={<span className="font-mono">{device.hwid}</span>}
            >
              <span className="text-[12px] tabular-nums text-muted-foreground">{formatDate(device.created_at, i18n.language)}</span>
              {canDelete && (
                <IconButton
                  size="8"
                  tone="danger"
                  data-row-button
                  disabled={isBusy}
                  onClick={() => void run(() => deleteDevice(device.hwid), t("subscriptions.devices.deleted"))}
                >
                  <Trash2 className="size-4" />
                </IconButton>
              )}
            </Row>
          ))}
      </DialogCard>
    </div>
  );
}
