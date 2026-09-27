import { AlertCircle, ChevronDown, ChevronRight, Filter, Inbox, Loader2, Repeat, Wallet } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  CURRENCY_SYMBOL,
  DEFAULT_PAGE_SIZE,
  PAYMENT_STATUS_BADGE_CLASSNAME,
  PURCHASE_TYPES,
  listPaymentOrderGateways,
  listPaymentOrders,
  type PaymentOrderItem,
  type PaymentOrderListFilters,
  type PaymentOrderStatus,
  type PurchaseType,
} from "@entities/payments/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PaymentOrderDetailsDialog } from "@features/payment-order-details/PaymentOrderDetailsDialog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { PeriodPills } from "@shared/ui/PeriodPills";
import type { PeriodDays } from "@shared/ui/PeriodToggle";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: PaymentOrderItem[]; total: number };

const STATUSES: PaymentOrderStatus[] = ["PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED"];
const FETCH_INDICATOR_DELAY_MS = 150;

const ROW_GRID_CLASSNAME = "grid grid-cols-[36px_minmax(0,1fr)_150px_80px_112px_16px] items-center gap-3";

interface DayGroup {
  key: string;
  date: Date;
  orders: PaymentOrderItem[];
}

// Orders arrive sorted by created_at desc, so consecutive grouping is enough.
function groupByDay(orders: PaymentOrderItem[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const order of orders) {
    const date = new Date(order.created_at);
    const key = date.toDateString();
    const last = groups[groups.length - 1];
    if (last?.key === key) last.orders.push(order);
    else groups.push({ key, date, orders: [order] });
  }
  return groups;
}

export function PaymentsPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [status, setStatus] = useState("");
  const [gatewayType, setGatewayType] = useState("");
  const [purchaseType, setPurchaseType] = useState("");
  const [period, setPeriod] = useState<PeriodDays>(0);
  // set by the header search's deep link; no local search box
  const [searchParams] = useSearchParams();
  const search = searchParams.get("search") ?? "";
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [detailsOrder, setDetailsOrder] = useState<PaymentOrderItem | null>(null);
  const [collapsedDays, setCollapsedDays] = useState<ReadonlySet<string>>(new Set());

  const toggleDay = (key: string) =>
    setCollapsedDays((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canViewDetails = permissions.includes("PAYMENTS_ORDER_VIEW");
  const canFilterByGateway = permissions.includes("PAYMENTS_GATEWAYS_VIEW");
  const [gatewayOptions, setGatewayOptions] = useState<string[]>([]);

  useEffect(() => {
    if (!canFilterByGateway) return;
    const controller = new AbortController();
    listPaymentOrderGateways(controller.signal)
      .then(setGatewayOptions)
      .catch(() => {});
    return () => controller.abort();
  }, [canFilterByGateway]);

  const baseFilters = useMemo<PaymentOrderListFilters>(
    () => ({
      status: (status || undefined) as PaymentOrderStatus | undefined,
      gatewayType: gatewayType || undefined,
      purchaseType: (purchaseType || undefined) as PurchaseType | undefined,
      createdFrom: period ? new Date(Date.now() - period * 86_400_000).toISOString() : undefined,
      search: search || undefined,
    }),
    [status, gatewayType, purchaseType, period, search],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listPaymentOrders({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
        }
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!controller.signal.aborted) setIsFetching(false);
      });
    return () => {
      controller.abort();
      clearTimeout(showFetchingTimeout);
    };
  }, [baseFilters]);

  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listPaymentOrders({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
      if (gen !== loadGenRef.current) return;
      setState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total }
          : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;
  const groups = useMemo(() => (state.kind === "ready" ? groupByDay(state.items) : []), [state]);

  const formatDay = (date: Date): string => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return t("payments.today");
    if (date.toDateString() === yesterday.toDateString()) return t("payments.yesterday");
    return date.toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "long",
      year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-48">
            <SelectDropdown
              id="payments-status"
              value={status}
              onChange={setStatus}
              icon={Filter}
              placeholder={t("payments.filters.statusAll")}
              options={[
                { value: "", label: t("payments.filters.statusAll") },
                ...STATUSES.map((value) => ({ value, label: t(`payments.status.${value}`) })),
              ]}
            />
          </div>
          {canFilterByGateway && (
            <div className="w-48">
              <SelectDropdown
                id="payments-gateway"
                value={gatewayType}
                onChange={setGatewayType}
                icon={Wallet}
                placeholder={t("payments.filters.gatewayAll")}
                options={[
                  { value: "", label: t("payments.filters.gatewayAll") },
                  ...gatewayOptions.map((type) => ({ value: type, label: t(`settings.gateways.types.${type}`) })),
                ]}
              />
            </div>
          )}
          <div className="w-48">
            <SelectDropdown
              id="payments-purchase-type"
              value={purchaseType}
              onChange={setPurchaseType}
              icon={Repeat}
              placeholder={t("payments.filters.purchaseTypeAll")}
              options={[
                { value: "", label: t("payments.filters.purchaseTypeAll") },
                ...PURCHASE_TYPES.map((type) => ({ value: type, label: t(`payments.purchaseType.${type}`) })),
              ]}
            />
          </div>
        </div>
        <PeriodPills value={period} onChange={setPeriod} ariaLabel={t("payments.columns.created")} />
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner className="py-12" />}
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
                <div
                  className={`${ROW_GRID_CLASSNAME} mb-1 border-b border-border px-3 pb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground`}
                >
                  <span className="col-span-2">{t("payments.columns.order")}</span>
                  <span>{t("payments.columns.amount")}</span>
                  <span>{t("payments.columns.created")}</span>
                  <span>{t("payments.columns.status")}</span>
                  <span />
                </div>
                <div className="flex flex-col gap-3">
                  {groups.map((group) => (
                    <section key={group.key} className="flex flex-col">
                      <h3>
                        <button
                          type="button"
                          aria-expanded={!collapsedDays.has(group.key)}
                          onClick={() => toggleDay(group.key)}
                          className="group flex w-full items-center gap-2.5 rounded-full px-3 py-1.5 text-left"
                        >
                          <ChevronDown
                            className={`size-3.5 text-muted-foreground transition-transform group-hover:text-foreground ${
                              collapsedDays.has(group.key) ? "-rotate-90" : ""
                            }`}
                          />
                          <span className="-ml-1 text-[12px] font-semibold text-foreground">{formatDay(group.date)}</span>
                          <span className="-ml-1 text-[11.5px] tabular-nums text-muted-foreground">
                            {group.orders.length}
                          </span>
                        </button>
                      </h3>
                      <div
                        className={`flex flex-col divide-y divide-border/50 ${collapsedDays.has(group.key) ? "hidden" : ""}`}
                      >
                        {group.orders.map((order) => {
                          const symbol = CURRENCY_SYMBOL[order.currency] ?? order.currency;
                          const gatewayLabel = t(`settings.gateways.types.${order.gateway_type}`);

                          return (
                            <motion.button
                              key={order.id}
                              type="button"
                              disabled={!canViewDetails}
                              onClick={() => setDetailsOrder(order)}
                              {...(canViewDetails && bounceTap(bounceStrength, 0.03))}
                              className={`${ROW_GRID_CLASSNAME} w-full rounded-full px-3 py-2.5 text-left [transition-property:background-color] duration-150 enabled:hover:bg-white/[0.04] disabled:cursor-default`}
                            >
                              <span
                                aria-hidden
                                className="flex size-9 items-center justify-center rounded-full bg-white/[0.06] text-[14px] font-semibold text-foreground"
                              >
                                {symbol}
                              </span>
                              <span className="min-w-0">
                                <span className="flex min-w-0 items-center gap-2">
                                  <span className="truncate text-[13.5px] font-medium text-foreground">
                                    {order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? "—"}
                                    {" · "}
                                    {order.duration_days}d
                                  </span>
                                  <span className="shrink-0 rounded-full border border-border px-2 py-px text-[10.5px] font-semibold text-muted-foreground">
                                    {t(`payments.purchaseType.${order.purchase_type}`)}
                                  </span>
                                </span>
                                <span className="block truncate font-mono text-[12px] text-muted-foreground">
                                  #{order.id} &middot; {gatewayLabel}
                                </span>
                              </span>
                              <span className="tabular-nums">
                                <span className="block text-[14px] font-semibold text-foreground">
                                  {symbol}
                                  {order.final_price}
                                </span>
                                {order.discount_percent > 0 && (
                                  <span className="block text-[11.5px] text-muted-foreground">
                                    <span className="line-through">
                                      {symbol}
                                      {order.base_price}
                                    </span>{" "}
                                    <span className="text-primary">−{order.discount_percent}%</span>
                                  </span>
                                )}
                              </span>
                              <span className="text-[13px] tabular-nums text-foreground">
                                {new Date(order.created_at).toLocaleTimeString(i18n.language, {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                              <span>
                                <span
                                  className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${PAYMENT_STATUS_BADGE_CLASSNAME[order.status]}`}
                                >
                                  {t(`payments.status.${order.status}`)}
                                </span>
                              </span>
                              {canViewDetails ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                            </motion.button>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
                {hasMore && (
                  <div className="mt-4 flex justify-center">
                    <motion.button
                      type="button"
                      onClick={() => void handleLoadMore()}
                      disabled={isLoadingMore}
                      aria-label={isLoadingMore ? t("payments.pagination.loadingMore") : undefined}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {!isLoadingMore && t("payments.pagination.loadMore")}
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
