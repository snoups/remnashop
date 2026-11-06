import { Smartphone, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  deleteAllSubscriptionDevices,
  deleteSubscriptionDevice,
  listSubscriptionDevices,
} from "@entities/subscriptions/api";
import { useAccountPermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { IconButton } from "@shared/ui/IconButton";
import { Spinner } from "@shared/ui/Spinner";

export function SubscriptionDevicesTab({ subscriptionId, userId }: { subscriptionId: number; userId: number }) {
  const { t, i18n } = useTranslation();
  const permissions = useAccountPermissions(userId);
  const canDelete = permissions.includes("SUBSCRIPTIONS_DEVICES_DELETE");
  const canDeleteAll = permissions.includes("SUBSCRIPTIONS_DEVICES_DELETE_ALL");
  const [state, reload, setData] = useAsyncResource((signal) => listSubscriptionDevices(subscriptionId, signal));
  const [isConfirmingAll, setIsConfirmingAll] = useState(false);
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
            <div key={device.hwid} className="flex w-full items-center gap-3 rounded-full px-2.5 py-2">
              <IconCircle icon={Smartphone} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-foreground/90">
                  {[device.device_model, device.platform].filter(Boolean).join(" · ") || t("common.none")}
                </span>
                <span className="block truncate font-mono text-[12px] text-muted-foreground">{device.hwid}</span>
              </span>
              <span className="shrink-0 text-[12px] tabular-nums text-muted-foreground">
                {formatDate(device.created_at, i18n.language)}
              </span>
              {canDelete && (
                <IconButton
                  size="8"
                  tone="danger"
                  disabled={isBusy}
                  onClick={() => void run(() => deleteDevice(device.hwid), t("subscriptions.devices.deleted"))}
                >
                  <Trash2 className="size-4" />
                </IconButton>
              )}
            </div>
          ))}
      </DialogCard>
      {canDeleteAll && state.kind === "ready" && state.data.items.length > 0 && (
        <div className="flex justify-end">
          <Button variant="glassDanger" disabled={isBusy} onClick={() => setIsConfirmingAll(true)}>
            {t("subscriptions.devices.deleteAll")}
          </Button>
        </div>
      )}
      {isConfirmingAll && (
        <ConfirmDialog
          title={t("subscriptions.devices.deleteAllTitle")}
          message={t("subscriptions.devices.deleteAllConfirm")}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsConfirmingAll(false);
            void run(() => deleteAllSubscriptionDevices(subscriptionId), t("subscriptions.devices.allDeleted"));
          }}
          onCancel={() => setIsConfirmingAll(false)}
        />
      )}
    </div>
  );
}
