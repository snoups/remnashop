import { Download, Upload, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getPanelSyncStatus,
  listMissingPanelSquads,
  startPanelSync,
  type MissingSquad,
  type PanelSyncDirection,
  type PanelSyncOptions,
  type PanelSyncResult,
  type PanelSyncStatus,
  type SquadReplacements,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Switch } from "@shared/ui/glass/Switch";

import { dropAllSquads } from "./drop-all-squads";
import { SquadReplacementsField } from "./SquadReplacements";

const POLL_INTERVAL_MS = 5_000;

const DEFAULT_OPTIONS: PanelSyncOptions = {
  adopt_unnamed: true,
  respect_subscription_limit: true,
  recreate_missing: true,
  delete_orphans: true,
};

const OPTIONS: Record<PanelSyncDirection, (keyof PanelSyncOptions)[]> = {
  FROM_PANEL: ["adopt_unnamed", "respect_subscription_limit"],
  TO_PANEL: ["recreate_missing", "delete_orphans"],
};

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
  const [options, setOptions] = useState<PanelSyncOptions>(DEFAULT_OPTIONS);
  const [missingSquads, setMissingSquads] = useState<MissingSquad[]>([]);
  const [replacements, setReplacements] = useState<SquadReplacements>({});
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

  const open = (direction: PanelSyncDirection) => {
    setOptions(DEFAULT_OPTIONS);
    setMissingSquads([]);
    setReplacements({});
    setConfirming(direction);
    if (direction !== "TO_PANEL" || !permissions.includes("SUBSCRIPTIONS_PANEL_MISSING_SQUADS_VIEW")) return;
    listMissingPanelSquads().then(
      ({ items }) => {
        setMissingSquads(items);
        setReplacements(dropAllSquads(items));
      },
      () => undefined,
    );
  };

  const start = async (direction: PanelSyncDirection) => {
    setConfirming(null);
    try {
      await startPanelSync(direction, options, direction === "TO_PANEL" ? replacements : {});
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
          onClick={() => open(direction)}
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
          size={confirming === "TO_PANEL" && missingSquads.length > 0 ? "md" : "sm"}
          onConfirm={() => void start(confirming)}
          onCancel={() => setConfirming(null)}
        >
          {OPTIONS[confirming].map((option) => (
            <div key={option} className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-3 text-[13px] text-foreground/80">
                <span>{t(`subscriptions.panelSync.bulk.options.${option}.label`)}</span>
                <Switch
                  checked={options[option]}
                  onChange={(on) => setOptions((current) => ({ ...current, [option]: on }))}
                />
              </div>
              <p className="text-[12px] text-muted-foreground">
                {t(`subscriptions.panelSync.bulk.options.${option}.hint`)}
              </p>
            </div>
          ))}
          {confirming === "TO_PANEL" && missingSquads.length > 0 && (
            <SquadReplacementsField missing={missingSquads} value={replacements} onChange={setReplacements} showHolders />
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}
