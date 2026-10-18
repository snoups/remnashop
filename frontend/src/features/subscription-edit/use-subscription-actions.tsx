import { Ban, CirclePlay, Link2, RefreshCw, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type SubscriptionListItem,
  disableSubscription,
  enableSubscription,
  reissueSubscriptionLink,
  resetSubscriptionTraffic,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import type { ActionMenuItem } from "@shared/ui/ActionMenu";
import { PanelSyncDialog } from "@features/subscription-edit/PanelSyncDialog";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

export function useSubscriptionActions(
  subscription: SubscriptionListItem,
  apply: (updated: SubscriptionListItem) => void,
) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const [isConfirmingReissue, setIsConfirmingReissue] = useState(false);
  const [isSyncingWithPanel, setIsSyncingWithPanel] = useState(false);

  const run = async (action: () => Promise<SubscriptionListItem>, done: string) => {
    try {
      apply(await action());
      toast.success(done);
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.actions.error")));
    }
  };

  const items: ActionMenuItem[] = [];
  if (subscription.status !== "DELETED") {
    if (permissions.includes("SUBSCRIPTIONS_STATUS_MANAGE")) {
      items.push(
        subscription.status === "DISABLED"
          ? {
              label: t("subscriptions.actions.enable"),
              icon: CirclePlay,
              onClick: () => void run(() => enableSubscription(subscription.id), t("subscriptions.actions.enabled")),
            }
          : {
              label: t("subscriptions.actions.disable"),
              icon: Ban,
              onClick: () => void run(() => disableSubscription(subscription.id), t("subscriptions.actions.disabled")),
            },
      );
    }
    if (permissions.includes("SUBSCRIPTIONS_TRAFFIC_RESET")) {
      items.push({
        label: t("subscriptions.actions.resetTraffic"),
        icon: RotateCcw,
        onClick: () => void run(() => resetSubscriptionTraffic(subscription.id), t("subscriptions.actions.trafficReset")),
      });
    }
    if (
      permissions.includes("SUBSCRIPTIONS_PANEL_DIFF_VIEW") &&
      (permissions.includes("SUBSCRIPTIONS_PULL_FROM_PANEL") || permissions.includes("SUBSCRIPTIONS_PUSH_TO_PANEL"))
    ) {
      items.push({
        label: t("subscriptions.panelSync.menuItem"),
        icon: RefreshCw,
        onClick: () => setIsSyncingWithPanel(true),
      });
    }
    if (permissions.includes("SUBSCRIPTIONS_LINK_REISSUE")) {
      items.push({
        label: t("subscriptions.actions.reissue"),
        icon: Link2,
        variant: "danger",
        separatorBefore: items.length > 0,
        onClick: () => setIsConfirmingReissue(true),
      });
    }
  }

  const confirm = isConfirmingReissue ? (
    <ConfirmDialog
      title={t("subscriptions.actions.reissueConfirmTitle")}
      message={t("subscriptions.actions.reissueConfirm")}
      confirmLabel={t("subscriptions.actions.reissue")}
      cancelLabel={t("common.cancel")}
      danger
      onConfirm={() => {
        setIsConfirmingReissue(false);
        void run(() => reissueSubscriptionLink(subscription.id), t("subscriptions.actions.reissued"));
      }}
      onCancel={() => setIsConfirmingReissue(false)}
    />
  ) : null;

  const panelSync = isSyncingWithPanel ? (
    <PanelSyncDialog
      subscription={subscription}
      onApplied={apply}
      onClose={() => setIsSyncingWithPanel(false)}
    />
  ) : null;

  return {
    items,
    confirm: (
      <>
        {confirm}
        {panelSync}
      </>
    ),
  };
}
