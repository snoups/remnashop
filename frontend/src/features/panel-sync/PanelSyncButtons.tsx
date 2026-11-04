import { Download, Upload, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getPanelSyncStatus,
  startPanelSync,
  type PanelSyncDirection,
  type PanelSyncResult,
  type PanelSyncStatus,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

const POLL_INTERVAL_MS = 5_000;

const DIRECTIONS: { direction: PanelSyncDirection; permission: "SUBSCRIPTIONS_PANEL_SYNC_FROM" | "SUBSCRIPTIONS_PANEL_SYNC_TO"; key: "pull" | "push"; icon: LucideIcon }[] = [
  { direction: "FROM_PANEL", permission: "SUBSCRIPTIONS_PANEL_SYNC_FROM", key: "pull", icon: Download },
  { direction: "TO_PANEL", permission: "SUBSCRIPTIONS_PANEL_SYNC_TO", key: "push", icon: Upload },
];

function isRunning(status: PanelSyncStatus | null, direction: PanelSyncDirection): boolean {
  if (status === null) return false;
  return (direction === "FROM_PANEL" ? status.from_panel : status.to_panel).running;
}

/** Bulk sync of every subscription with the panel, one button per direction. */
export function PanelSyncButtons({ onFinished }: { onFinished: () => void }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const [status, setStatus] = useState<PanelSyncStatus | null>(null);
  const [confirming, setConfirming] = useState<PanelSyncDirection | null>(null);
  const previous = useRef<PanelSyncStatus | null>(null);

  const canView = permissions.includes("SUBSCRIPTIONS_PANEL_SYNC_STATUS_VIEW");
  const allowed = DIRECTIONS.filter((d) => permissions.includes(d.permission));

  const announce = useCallback(
    (result: PanelSyncResult) => {
      const key =
        result.direction === "TO_PANEL"
          ? "subscriptions.panelSync.bulk.finishedToPanel"
          : "subscriptions.panelSync.bulk.finished";
      toast.success(t(key, { ...result }));
      onFinished();
    },
    [onFinished, t],
  );

  const load = useCallback(() => {
    if (!canView) return;
    getPanelSyncStatus().then(
      (next) => {
        for (const { direction } of DIRECTIONS) {
          const last = direction === "FROM_PANEL" ? next.from_panel.last : next.to_panel.last;
          if (isRunning(previous.current, direction) && !isRunning(next, direction) && last) announce(last);
        }
        previous.current = next;
        setStatus(next);
      },
      () => undefined,
    );
  }, [announce, canView]);

  useEffect(load, [load]);

  const anyRunning = DIRECTIONS.some(({ direction }) => isRunning(status, direction));
  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [anyRunning, load]);

  if (allowed.length === 0) return null;

  const start = async (direction: PanelSyncDirection) => {
    setConfirming(null);
    try {
      await startPanelSync(direction);
      toast.success(t("subscriptions.panelSync.bulk.started"));
      load();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.panelSync.bulk.error")));
    }
  };

  const confirmKey = DIRECTIONS.find((d) => d.direction === confirming)?.key;

  return (
    <div className="flex items-center gap-2">
      {allowed.map(({ direction, key, icon }) => (
        <Button
          key={direction}
          variant="glass"
          icon={icon}
          isLoading={isRunning(status, direction)}
          onClick={() => setConfirming(direction)}
        >
          {t(`subscriptions.panelSync.bulk.${key}`)}
        </Button>
      ))}
      {confirming !== null && confirmKey && (
        <ConfirmDialog
          title={t(`subscriptions.panelSync.bulk.${confirmKey}Title`)}
          message={t(`subscriptions.panelSync.bulk.${confirmKey}Confirm`)}
          confirmLabel={t(`subscriptions.panelSync.bulk.${confirmKey}Action`)}
          cancelLabel={t("common.cancel")}
          danger={confirming === "TO_PANEL"}
          onConfirm={() => void start(confirming)}
          onCancel={() => setConfirming(null)}
        />
      )}
    </div>
  );
}
