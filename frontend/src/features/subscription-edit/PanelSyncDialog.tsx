import type { ParseKeys } from "i18next";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getSubscriptionPanelDiff,
  pullSubscriptionFromPanel,
  pushSubscriptionToPanel,
  type SubscriptionListItem,
  type SubscriptionPanelDiff,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Spinner } from "@shared/ui/Spinner";

// machine values the panel and the shop store verbatim
const MONO_FIELDS: ReadonlySet<string> = new Set(["url", "internal_squads", "external_squad", "telegram_id"]);

type DiffState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; diff: SubscriptionPanelDiff };

interface PanelSyncDialogProps {
  subscription: SubscriptionListItem;
  onApplied: (updated: SubscriptionListItem) => void;
  onClose: () => void;
}

export function PanelSyncDialog({ subscription, onApplied, onClose }: PanelSyncDialogProps) {
  return (
    <Modal onClose={onClose} size="md">
      <PanelSyncBody subscription={subscription} onApplied={onApplied} />
    </Modal>
  );
}

function PanelSyncBody({ subscription, onApplied }: Omit<PanelSyncDialogProps, "onClose">) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const close = useModalClose();
  const [state, setState] = useState<DiffState>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getSubscriptionPanelDiff(subscription.id, controller.signal).then(
      (diff) => setState({ kind: "ready", diff }),
      () => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      },
    );
    return () => controller.abort();
  }, [subscription.id]);

  const run = async (action: () => Promise<SubscriptionListItem>, done: string) => {
    setBusy(true);
    try {
      onApplied(await action());
      toast.success(done);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.panelSync.error")));
    } finally {
      setBusy(false);
    }
  };

  const canPull = permissions.includes("SUBSCRIPTIONS_PULL_FROM_PANEL");
  const canPush = permissions.includes("SUBSCRIPTIONS_PUSH_TO_PANEL");
  const missing = state.kind === "ready" && state.diff.missing_in_panel;
  const inSync = state.kind === "ready" && !missing && state.diff.fields.length === 0;

  return (
    <>
      <DialogHeader icon={RefreshCw} title={t("subscriptions.panelSync.title")} />

      <div className="p-4">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {missing && <p className="text-[13px] text-foreground/80">{t("subscriptions.panelSync.missing")}</p>}
        {inSync && <p className="text-[13px] text-foreground/80">{t("subscriptions.panelSync.inSync")}</p>}
        {state.kind === "ready" && state.diff.fields.length > 0 && (
          <div className="flex flex-col gap-1.5 text-[12px]">
            <div className="grid grid-cols-3 gap-3 text-muted-foreground">
              <span>{t("subscriptions.panelSync.columns.field")}</span>
              <span>{t("subscriptions.panelSync.columns.shop")}</span>
              <span>{t("subscriptions.panelSync.columns.panel")}</span>
            </div>
            {state.diff.fields.map((diff) => {
              const valueClass = `break-all ${MONO_FIELDS.has(diff.field) ? "font-mono text-[12px]" : ""}`;
              return (
                <div key={diff.field} className="grid grid-cols-3 gap-3">
                  <span>{t(`subscriptions.panelSync.fieldNames.${diff.field}` as ParseKeys)}</span>
                  <span className={valueClass}>{diff.shop || t("common.none")}</span>
                  <span className={valueClass}>{diff.panel || t("common.none")}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className={GLASS_DIALOG_FOOTER_CLASS}>
        {canPull && (
          <Button
            variant="glass"
            className="flex-1"
            disabled={busy || state.kind !== "ready" || inSync}
            onClick={() =>
              void run(() => pullSubscriptionFromPanel(subscription.id), t("subscriptions.panelSync.pulled"))
            }
          >
            {t("subscriptions.panelSync.pull")}
          </Button>
        )}
        {canPush && (
          <Button
            variant="glassAccent"
            className="flex-1"
            disabled={busy || state.kind !== "ready" || inSync}
            onClick={() =>
              void run(() => pushSubscriptionToPanel(subscription.id), t("subscriptions.panelSync.pushed"))
            }
          >
            {t("subscriptions.panelSync.push")}
          </Button>
        )}
      </div>
    </>
  );
}
