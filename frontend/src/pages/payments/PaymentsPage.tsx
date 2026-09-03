import { AlertCircle, ChevronDown, CreditCard, Filter, Inbox, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  CURRENCY_SYMBOL,
  DEFAULT_PAGE_SIZE,
  listPaymentOrders,
  type PaymentOrderItem,
  type PaymentOrderStatus,
} from "@entities/payments/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PaymentOrderDetailsDialog } from "@features/payment-order-details/PaymentOrderDetailsDialog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: PaymentOrderItem[]; total: number };

const STATUSES: PaymentOrderStatus[] = ["PENDING", "PAID", "FAILED", "EXPIRED", "CANCELED"];
const LOAD_MORE_STEP = 10;
const FETCH_INDICATOR_DELAY_MS = 150;

const STATUS_BADGE_CLASSNAME: Record<PaymentOrderStatus, string> = {
  PAID: "border-success/30 bg-success/10 text-success",
  PENDING: "border-warning/30 bg-warning/10 text-warning",
  FAILED: "border-error/30 bg-error/10 text-error",
  EXPIRED: "border-border bg-white/[0.04] text-muted-foreground",
  CANCELED: "border-border bg-white/[0.04] text-muted-foreground",
};

function formatExpireDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

export function PaymentsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [status, setStatus] = useState("");
  const [visibleCount, setVisibleCount] = useState(DEFAULT_PAGE_SIZE);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [detailsOrder, setDetailsOrder] = useState<PaymentOrderItem | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canViewDetails = permissions.includes("PAYMENTS_ORDER_VIEW");

  const baseFilters = useMemo<{ status?: PaymentOrderStatus }>(
    () => ({ status: (status || undefined) as PaymentOrderStatus | undefined }),
    [status],
  );

  useEffect(() => {
    let cancelled = false;
    const showFetchingTimeout = setTimeout(() => {
      if (!cancelled) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    setVisibleCount(DEFAULT_PAGE_SIZE);
    listPaymentOrders({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE })
      .then((result) => {
        if (!cancelled) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
        }
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!cancelled) setIsFetching(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(showFetchingTimeout);
    };
  }, [baseFilters]);

  const handleLoadMore = async () => {
    const nextCount = visibleCount + LOAD_MORE_STEP;
    setIsLoadingMore(true);
    try {
      const result = await listPaymentOrders({ ...baseFilters, page: 1, pageSize: nextCount });
      setState({ kind: "ready", items: result.items, total: result.total });
      setVisibleCount(nextCount);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("payments.filters.status")}
            </label>
            <SelectDropdown
              id="payments-status"
              value={status}
              onChange={setStatus}
              icon={Filter}
              placeholder={t("payments.filters.statusAll")}
              options={[
                { value: "", label: t("payments.filters.statusAll") },
                ...STATUSES.map((s) => ({ value: s, label: t(`payments.status.${s}`) })),
              ]}
            />
          </div>
        </div>
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <p className="text-sm">{t("payments.loading")}</p>
          </div>
        )}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("payments.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("payments.empty")}</p>
              </div>
            )}
            {state.items.length > 0 && (
              <>
                <div className="flex flex-col divide-y divide-border/50">
                  {state.items.map((order) => {
                    const symbol = CURRENCY_SYMBOL[order.currency] ?? order.currency;
                    const hasDiscount = order.discount_percent > 0;

                    const menuItems: ActionMenuItem[] = [];
                    if (canViewDetails) {
                      menuItems.push({
                        label: t("payments.details.button"),
                        icon: Info,
                        onClick: () => setDetailsOrder(order),
                      });
                    }

                    return (
                      <div
                        key={order.id}
                        className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                            <CreditCard className="size-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-[13.5px] font-medium text-foreground">
                              {order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? "—"}
                              {" · "}
                              {order.duration_days}d
                            </p>
                            <p className="truncate font-mono text-[12px] text-muted-foreground">
                              {t("payments.orderLabel", { id: order.id })} &middot; #{order.user_id} &middot;{" "}
                              {t(`settings.gateways.types.${order.gateway_type}`)}
                            </p>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-4">
                          <div className="text-right">
                            <p className="text-[14px] font-semibold text-foreground">
                              {hasDiscount && (
                                <span className="mr-1.5 text-[12px] font-normal text-muted-foreground line-through">
                                  {symbol}
                                  {order.base_price}
                                </span>
                              )}
                              {symbol}
                              {order.final_price}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px] text-muted-foreground">{t("payments.fields.expires")}</p>
                            <p className="text-[13px] font-medium text-foreground">
                              {formatExpireDate(order.expires_at)}
                            </p>
                          </div>
                          <span
                            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${STATUS_BADGE_CLASSNAME[order.status]}`}
                          >
                            {t(`payments.status.${order.status}`)}
                          </span>
                          {menuItems.length > 0 && <ActionMenu items={menuItems} />}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {hasMore && (
                  <div className="mt-4 flex justify-center">
                    <motion.button
                      type="button"
                      onClick={() => void handleLoadMore()}
                      disabled={isLoadingMore}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {isLoadingMore ? t("payments.pagination.loadingMore") : t("payments.pagination.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {detailsOrder && <PaymentOrderDetailsDialog order={detailsOrder} onClose={() => setDetailsOrder(null)} />}
    </div>
  );
}
