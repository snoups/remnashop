import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { listAddons } from "@entities/addons/api";
import { type Plan, getPlan, listPlans } from "@entities/plans/api";
import { useAnchorCurrency } from "@entities/pricing/use-anchor-currency";
import { type Promocode, getPromocode } from "@entities/promocodes/api";
import { type SubscriptionListItem, getSubscription } from "@entities/subscriptions/api";
import { type TransactionItem, getTransaction } from "@entities/transactions/api";
import { type UserListItem, getUser } from "@entities/user/api";
import { PlanEditDialog } from "@features/plan-edit/PlanEditDialog";
import { PromocodeDetailsDialog } from "@features/promocode-details/PromocodeDetailsDialog";
import { SubscriptionEditDialog } from "@features/subscription-edit/SubscriptionEditDialog";
import { TransactionDetailsDialog } from "@features/transaction-details/TransactionDetailsDialog";
import { UserDetailsDialog, type UserDetailsTab } from "@features/user-details/UserDetailsDialog";
import { ApiError, getErrorMessage } from "@shared/api/http";
import {
  EntityDialogContext,
  type EntityDialogRequest,
  type EntityKind,
  notifyEntityChanged,
} from "@shared/lib/entity-dialogs";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ParentPanelContext } from "@shared/ui/modal-hooks";

const FETCHERS: Record<EntityKind, (id: number, signal: AbortSignal) => Promise<unknown>> = {
  user: getUser,
  order: getTransaction,
  subscription: getSubscription,
  promocode: getPromocode,
  plan: getPlan,
};

interface OpenDialog extends EntityDialogRequest {
  key: number;
}

/** Renders entity dialogs requested through useOpenEntity(), stacked in the order they were opened. */
export function EntityDialogHost({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<OpenDialog[]>([]);
  const nextKeyRef = useRef(0);

  const open = useCallback((request: EntityDialogRequest) => {
    nextKeyRef.current += 1;
    const key = nextKeyRef.current;
    setStack((current) => [...current, { ...request, key }]);
  }, []);

  return (
    <EntityDialogContext.Provider value={open}>
      {children}
      {stack.map((request) => (
        <ParentPanelContext.Provider key={request.key} value={request.parentPanel ?? null}>
          <EntityDialog
            request={request}
            onClose={() => setStack((current) => current.filter((other) => other.key !== request.key))}
          />
        </ParentPanelContext.Provider>
      ))}
    </EntityDialogContext.Provider>
  );
}

function EntityDialog({ request, onClose }: { request: OpenDialog; onClose: () => void }) {
  const { t } = useTranslation();
  const [entity, setEntity] = useState<unknown>(request.data ?? null);

  useEffect(() => {
    if (request.data !== undefined) return;
    const controller = new AbortController();
    FETCHERS[request.kind](request.id, controller.signal)
      .then(setEntity)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        toast.error(
          err instanceof ApiError && err.status === 404
            ? t("header.entityNotFound")
            : getErrorMessage(err, t("common.errors.generic")),
        );
        onClose();
      });
    return () => controller.abort();
    // one fetch per opened dialog
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (entity === null) return null;
  const onChanged = () => {
    request.onChanged?.();
    notifyEntityChanged(request.kind);
  };

  switch (request.kind) {
    case "user":
      return (
        <UserDetailsDialog
          user={entity as UserListItem}
          initialTab={request.tab as UserDetailsTab | undefined}
          onChanged={onChanged}
          onDeleted={onChanged}
          onClose={onClose}
        />
      );
    case "order":
      return <TransactionDetailsDialog order={entity as TransactionItem} onClose={onClose} />;
    case "subscription":
      return (
        <SubscriptionEditDialog
          subscription={entity as SubscriptionListItem}
          onSaved={onChanged}
          onDeleted={onChanged}
          onClose={onClose}
        />
      );
    case "promocode":
      return <PromocodeDialog promocode={entity as Promocode} onChanged={onChanged} onClose={onClose} />;
    case "plan":
      return <PlanDialog plan={entity as Plan} onChanged={onChanged} onClose={onClose} />;
  }
}

// the reward line names add-ons and plans, so both lists load before the dialog shows
function PromocodeDialog({
  promocode,
  onChanged,
  onClose,
}: {
  promocode: Promocode;
  onChanged?: () => void;
  onClose: () => void;
}) {
  const [state] = useAsyncResource(async (signal) => {
    const orEmpty = <T,>(promise: Promise<T[]>) => promise.catch(() => [] as T[]);
    const [addons, plans] = await Promise.all([orEmpty(listAddons(signal)), orEmpty(listPlans(signal))]);
    return { addons, plans };
  });

  if (state.kind !== "ready") return null;
  const catalog = state.data;
  return (
    <PromocodeDetailsDialog
      promocode={promocode}
      addons={catalog.addons}
      plans={catalog.plans}
      onSaved={onChanged}
      onDeleted={onChanged}
      onClose={onClose}
    />
  );
}

function PlanDialog({ plan, onChanged, onClose }: { plan: Plan; onChanged?: () => void; onClose: () => void }) {
  const anchorCurrency = useAnchorCurrency();
  return <PlanEditDialog plan={plan} anchorCurrency={anchorCurrency} onSaved={() => onChanged?.()} onClose={onClose} />;
}
