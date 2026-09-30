import {
  AlertCircle,
  ArrowLeftRight,
  ChevronRight,
  Filter,
  Loader2,
  RefreshCw,
  Repeat,
  Sparkles,
  Wallet,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import {
  CURRENCY_SYMBOL,
  DEFAULT_PAGE_SIZE,
  getPaymentOrderSummary,
  PAYMENT_STATUS_BADGE_TONE,
  PAYMENT_STATUS_DOT_CLASSNAME,
  PAYMENT_STATUS_ICON_CLASSNAME,
  PURCHASE_TYPES,
  listPaymentOrderGateways,
  listPaymentOrders,
  type PaymentOrderItem,
  type PaymentOrderListFilters,
  type PaymentOrderStatus,
  type PaymentOrderSummary,
  type PurchaseType,
} from "@entities/payments/api";
import { formatMoney, formatPercent } from "@entities/advertising/format";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PaymentOrderDetailsDialog } from "@features/payment-order-details/PaymentOrderDetailsDialog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { EmptyState } from "@shared/ui/EmptyState";
import { KpiTile, type KpiTrend } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { dotIcon, letterIcon } from "@shared/ui/optionIcons";
import { PeriodPills, type PeriodDays } from "@shared/ui/PeriodPills";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { Tag } from "@shared/ui/Tag";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: PaymentOrderItem[]; total: number };

const STATUSES: PaymentOrderStatus[] = ["PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED"];
const FETCH_INDICATOR_DELAY_MS = 150;
const DAY_MS = 86_400_000;
// "all time" has no previous window; show growth over the last month instead
const ALL_TIME_TREND_DAYS = 30;

const STATUS_DOT_ICONS = Object.fromEntries(
  STATUSES.map((value) => [value, dotIcon(PAYMENT_STATUS_DOT_CLASSNAME[value])]),
) as Record<PaymentOrderStatus, ReturnType<typeof dotIcon>>;
const PURCHASE_TYPE_ICONS: Record<PurchaseType, ComponentType<{ className?: string }>> = {
  NEW: Sparkles,
  RENEW: RefreshCw,
  CHANGE: ArrowLeftRight,
};

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
  const [summary, setSummary] = useState<PaymentOrderSummary | null>(null);
  // the previous window of the same length, or the last 30 days for "all time"
  const [compareSummary, setCompareSummary] = useState<PaymentOrderSummary | null>(null);
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
      createdFrom: period ? new Date(Date.now() - period * DAY_MS).toISOString() : undefined,
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

  useEffect(() => {
    const controller = new AbortController();
    getPaymentOrderSummary(baseFilters, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setSummary(result);
      })
      .catch(() => {
        // metrics are secondary; the list stays usable with dashes in their place
      });
    return () => controller.abort();
  }, [baseFilters]);

  useEffect(() => {
    const controller = new AbortController();
    const now = Date.now();
    setCompareSummary(null);
    getPaymentOrderSummary(
      period
        ? {
            ...baseFilters,
            createdFrom: new Date(now - 2 * period * DAY_MS).toISOString(),
            createdTo: new Date(now - period * DAY_MS).toISOString(),
          }
        : { ...baseFilters, createdFrom: new Date(now - ALL_TIME_TREND_DAYS * DAY_MS).toISOString() },
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setCompareSummary(result);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [baseFilters, period]);

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

  const none = t("payments.stats.none");
  const money = (amount: string) => formatMoney(amount, summary?.report_currency ?? "", i18n.language);

  const trendHint = period ? t("payments.stats.periodTrend", { days: period }) : t("payments.stats.totalTrend");
  const countTrend = (pick: (s: PaymentOrderSummary) => number): KpiTrend | undefined =>
    summary && compareSummary
      ? { delta: period ? pick(summary) - pick(compareSummary) : pick(compareSummary), hint: trendHint }
      : undefined;
  const percentTrend = (current: number, base: number): KpiTrend | undefined => {
    if (!(base > 0)) return undefined; // also NaN from 0/0
    const delta = current / base - 1;
    return { delta, text: formatPercent(String(Math.abs(delta)), i18n.language), hint: trendHint };
  };
  const revenueTrend =
    summary && compareSummary
      ? period
        ? percentTrend(Number(summary.revenue), Number(compareSummary.revenue))
        : // all time: last 30 days against everything before them
          percentTrend(Number(summary.revenue), Number(summary.revenue) - Number(compareSummary.revenue))
      : undefined;
  const averageCheckTrend =
    summary?.average_check != null && compareSummary?.average_check != null
      ? period
        ? percentTrend(Number(summary.average_check), Number(compareSummary.average_check))
        : // all time: last 30 days' average against the average of everything before them
          percentTrend(
            Number(compareSummary.average_check),
            (Number(summary.revenue) - Number(compareSummary.revenue)) /
              (summary.paid_count - compareSummary.paid_count),
          )
      : undefined;

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
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile
          label={t("payments.stats.orders")}
          value={summary ? String(summary.total_count) : none}
          trend={countTrend((s) => s.total_count)}
          hint={summary ? t("payments.stats.pending", { count: summary.pending_count }) : undefined}
        />
        <KpiTile
          label={t("payments.stats.paid")}
          value={summary ? String(summary.paid_count) : none}
          trend={countTrend((s) => s.paid_count)}
          hint={
            summary
              ? `${t("payments.stats.conversionRate")} ${formatPercent(summary.conversion_rate, i18n.language)}`
              : undefined
          }
        />
        <KpiTile
          label={t("payments.stats.averageCheck")}
          value={summary?.average_check != null ? money(summary.average_check) : none}
          trend={averageCheckTrend}
          hint={
            summary?.average_discount != null
              ? `${t("payments.stats.averageDiscount")} ${formatPercent(summary.average_discount, i18n.language)}`
              : undefined
          }
        />
        <KpiTile
          label={t("payments.stats.revenue")}
          value={summary ? money(summary.revenue) : none}
          trend={revenueTrend}
          hint={
            summary && Number(summary.refunded_amount) > 0
              ? `${t("payments.stats.refunded")} ${money(summary.refunded_amount)}`
              : undefined
          }
        />
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>
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
                ...STATUSES.map((value) => ({
                  value,
                  label: t(`payments.status.${value}`),
                  icon: STATUS_DOT_ICONS[value],
                })),
              ]}
            />
          </div>
          {canFilterByGateway && (
            <div className="flex min-w-40 flex-1 flex-col gap-1.5">
              <label className={EYEBROW_CLASS}>
                {t("payments.filters.gateway")}
              </label>
              <SelectDropdown
                id="payments-gateway"
                value={gatewayType}
                onChange={setGatewayType}
                icon={Wallet}
                placeholder={t("payments.filters.gatewayAll")}
                options={[
                  { value: "", label: t("payments.filters.gatewayAll") },
                  ...gatewayOptions.map((type) => {
                    const label = t(`settings.gateways.types.${type}`);
                    return { value: type, label, icon: letterIcon(label) };
                  }),
                ]}
              />
            </div>
          )}
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>
              {t("payments.filters.purchaseType")}
            </label>
            <SelectDropdown
              id="payments-purchase-type"
              value={purchaseType}
              onChange={setPurchaseType}
              icon={Repeat}
              placeholder={t("payments.filters.purchaseTypeAll")}
              options={[
                { value: "", label: t("payments.filters.purchaseTypeAll") },
                ...PURCHASE_TYPES.map((type) => ({
                  value: type,
                  label: t(`payments.purchaseType.${type}`),
                  icon: PURCHASE_TYPE_ICONS[type],
                })),
              ]}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className={EYEBROW_CLASS}>{t("payments.filters.period")}</span>
            <PeriodPills value={period} onChange={setPeriod} ariaLabel={t("payments.filters.period")} />
          </div>
        </div>
      </Card>

      <Card className="relative">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("payments.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <EmptyState text={t("payments.empty")} size="page" />
            )}
            {state.items.length > 0 && (
              <>
                <div
                  className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}
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
                        <GroupToggle
                          open={!collapsedDays.has(group.key)}
                          onToggle={() => toggleDay(group.key)}
                          label={formatDay(group.date)}
                          count={group.orders.length}
                        />
                      </h3>
                      <Collapse open={!collapsedDays.has(group.key)} className={`${LIST_BODY_CLASS}`}>
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
                              className={`${ROW_GRID_CLASSNAME} w-full ${LIST_ROW_CLASS} text-left enabled:hover:bg-white/[0.04] disabled:cursor-default`}
                            >
                              <span
                                aria-hidden
                                className={`flex size-9 items-center justify-center rounded-full text-[14px] font-semibold ${PAYMENT_STATUS_ICON_CLASSNAME[order.status]}`}
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
                                  <Tag>
                                    {t(`payments.purchaseType.${order.purchase_type}`)}
                                  </Tag>
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
                                <Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>
                                  {t(`payments.status.${order.status}`)}
                                </Badge>
                              </span>
                              {canViewDetails ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                            </motion.button>
                          );
                        })}
                      </Collapse>
                    </section>
                  ))}
                </div>
                {state.kind === "ready" && hasMore && (
                  <div className="mx-3 mt-4">
                    <LoadMoreButton
                      onClick={() => void handleLoadMore()}
                      isLoading={isLoadingMore}
                      shown={state.items.length}
                      total={state.total}
                    />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </Card>

      {detailsOrder && <PaymentOrderDetailsDialog order={detailsOrder} onClose={() => setDetailsOrder(null)} />}
    </div>
  );
}
