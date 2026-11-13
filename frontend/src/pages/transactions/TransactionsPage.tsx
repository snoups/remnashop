import type { ParseKeys } from "i18next";
import {
  ArrowLeftRight,
  Calculator,
  CalendarRange,
  ChevronRight,
  CircleCheck,
  Filter,
  PackageX,
  Receipt,
  RefreshCw,
  Repeat,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useMemo, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { DEFAULT_PAGE_SIZE, getTransactionSummary, hasDiscount, totalDiscountPercent, PAYMENT_STATUS_BADGE_TONE, PAYMENT_STATUS_DOT_CLASSNAME, PURCHASE_TYPES, listTransactionGateways, listTransactionsAfter, UNFULFILLED_STATUS, type TransactionItem, type TransactionListFilters, type TransactionStatus, type TransactionSummary, type PurchaseType } from "@entities/transactions/api";
import { userName } from "@entities/user/display";
import { usePermissions } from "@entities/user/use-current-user";
import { TransactionDetailsDialog } from "@features/transaction-details/TransactionDetailsDialog";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ALL_TIME_TREND_DAYS, DAY_MS, PERIOD_DAYS, type PeriodDays } from "@shared/lib/period";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { currencySymbol, formatMoney, formatPercent } from "@shared/lib/format";
import { formatTime } from "@shared/lib/relative-time";
import { formatDayLabel, groupByDay } from "@shared/lib/day-groups";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile, type KpiTrend } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { dotIcon, letterIcon } from "@shared/ui/option-icons";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { ListRow } from "@shared/ui/ListRow";

const STATUSES: TransactionStatus[] = ["PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED"];

const STATUS_DOT_ICONS = Object.fromEntries(
  STATUSES.map((value) => [value, dotIcon(PAYMENT_STATUS_DOT_CLASSNAME[value])]),
) as Record<TransactionStatus, ReturnType<typeof dotIcon>>;
const PURCHASE_TYPE_ICONS: Record<PurchaseType, ComponentType<{ className?: string }>> = {
  NEW: Sparkles,
  RENEW: RefreshCw,
  CHANGE: ArrowLeftRight,
};

const ROW_GRID_CLASSNAME = "grid grid-cols-[32px_minmax(0,1fr)_140px_150px_80px_112px_16px] items-center gap-3";

const STATUS_FILTERS: readonly string[] = [...STATUSES, UNFULFILLED_STATUS];

export function TransactionsPage() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  // `?status=` comes from the overview's attention links
  const [status, setStatus] = useState(() => {
    const fromUrl = searchParams.get("status") ?? "";
    return STATUS_FILTERS.includes(fromUrl) ? fromUrl : "";
  });
  const [gatewayType, setGatewayType] = useState("");
  const [purchaseType, setPurchaseType] = useState("");
  const [period, setPeriod] = useState<PeriodDays>(0);
  const [detailsOrder, setDetailsOrder] = useState<TransactionItem | null>(null);
  const permissions = usePermissions();
  const canViewDetails = permissions.includes("TRANSACTIONS_DETAIL_VIEW");
  const canFilterByGateway = permissions.includes("TRANSACTIONS_GATEWAYS_VIEW");
  const [gatewaysState] = useAsyncResource(
    (signal) => (canFilterByGateway ? listTransactionGateways(signal) : Promise.resolve([])),
    { deps: [canFilterByGateway], keepData: true },
  );
  const gatewayOptions = gatewaysState.kind === "ready" ? gatewaysState.data : [];

  const hasFilters = Boolean(status || gatewayType || purchaseType || period);
  const baseFilters = useMemo<TransactionListFilters>(
    () => ({
      status: (status && status !== UNFULFILLED_STATUS ? status : undefined) as TransactionStatus | undefined,
      unfulfilled: status === UNFULFILLED_STATUS || undefined,
      gatewayType: gatewayType || undefined,
      purchaseType: (purchaseType || undefined) as PurchaseType | undefined,
      createdFrom: period ? new Date(Date.now() - period * DAY_MS).toISOString() : undefined,
    }),
    [status, gatewayType, purchaseType, period],
  );

  const { state, setState, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore } = usePaginatedList(
    (filters, _page, signal, loaded?: TransactionItem[]) =>
      listTransactionsAfter({ ...filters, pageSize: DEFAULT_PAGE_SIZE }, loaded, signal),
    baseFilters,
  );

  const [summaryState, reloadSummary] = useAsyncResource((signal) => getTransactionSummary(baseFilters, signal), {
    deps: [baseFilters],
    keepData: true,
  });
  // the previous window of the same length; for "all time", the last ALL_TIME_TREND_DAYS days
  const [compareState, reloadCompare] = useAsyncResource(
    (signal) => {
      const now = Date.now();
      return getTransactionSummary(
        period
          ? {
              ...baseFilters,
              createdFrom: new Date(now - 2 * period * DAY_MS).toISOString(),
              createdTo: new Date(now - period * DAY_MS).toISOString(),
            }
          : { ...baseFilters, createdFrom: new Date(now - ALL_TIME_TREND_DAYS * DAY_MS).toISOString() },
        signal,
      );
    },
    { deps: [baseFilters, period] },
  );
  const summary = summaryState.kind === "ready" ? summaryState.data : null;
  const compareSummary = compareState.kind === "ready" ? compareState.data : null;

  const groups = useMemo(
    () => (state.kind === "ready" ? groupByDay(state.items, (item) => item.created_at) : []),
    [state],
  );
  const [collapsedDays, toggleDay] = useCollapsedSet();

  const none = t("common.none");
  const money = (amount: string) => formatMoney(amount, summary?.report_currency ?? "", i18n.language);

  const trendHint = period ? t("transactions.stats.periodTrend", { days: period }) : t("transactions.stats.totalTrend");
  const countTrend = (pick: (s: TransactionSummary) => number): KpiTrend | undefined =>
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

  return (
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="transactions-status"
            value={status}
            onChange={setStatus}
            icon={Filter}
            size="compact"
            glassPopover
            placeholder={t("transactions.filters.statusAll")}
            options={[
              { value: "", label: t("transactions.filters.statusAll"), icon: Filter },
              ...STATUSES.map((value) => ({
                value,
                label: t(`transactions.status.${value}`),
                icon: STATUS_DOT_ICONS[value],
              })),
              { value: UNFULFILLED_STATUS, label: t("transactions.filters.unfulfilled"), icon: PackageX },
            ]}
          />
        </div>
        {canFilterByGateway && (
          <div className="min-w-40 flex-1 md:min-w-0">
            <SelectDropdown
              id="transactions-gateway"
              value={gatewayType}
              onChange={setGatewayType}
              icon={Wallet}
              size="compact"
              glassPopover
              placeholder={t("transactions.filters.gatewayAll")}
              options={[
                { value: "", label: t("transactions.filters.gatewayAll"), icon: Wallet },
                ...gatewayOptions.map((type) => {
                  const label = t(`settings.gateways.types.${type}` as ParseKeys);
                  return { value: type, label, icon: letterIcon(label) };
                }),
              ]}
            />
          </div>
        )}
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="transactions-purchase-type"
            value={purchaseType}
            onChange={setPurchaseType}
            icon={Repeat}
            size="compact"
            glassPopover
            placeholder={t("transactions.filters.purchaseTypeAll")}
            options={[
              { value: "", label: t("transactions.filters.purchaseTypeAll"), icon: Repeat },
              ...PURCHASE_TYPES.map((type) => ({
                value: type,
                label: t(`transactions.purchaseType.${type}`),
                icon: PURCHASE_TYPE_ICONS[type],
              })),
            ]}
          />
        </div>
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="transactions-period"
            value={String(period)}
            onChange={(value) => setPeriod(Number(value) as PeriodDays)}
            icon={CalendarRange}
            size="compact"
            glassPopover
            placeholder={t("dashboard.periodAll")}
            options={PERIOD_DAYS.map((days) => ({
              value: String(days),
              label: days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days }),
              icon: CalendarRange,
            }))}
          />
        </div>
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading" || summaryState.kind === "loading"} />
      <div className="flex flex-col gap-5">
      <div className="grid shrink-0 grid-cols-2 gap-5 lg:grid-cols-4">
        <KpiTile
          panel
          icon={Receipt}
          label={t("transactions.stats.orders")}
          value={summary ? String(summary.total_count) : none}
          trend={countTrend((s) => s.total_count)}
          hint={summary ? t("transactions.stats.pending", { count: summary.pending_count }) : undefined}
        />
        <KpiTile
          panel
          icon={CircleCheck}
          label={t("transactions.stats.paid")}
          value={summary ? String(summary.paid_count) : none}
          trend={countTrend((s) => s.paid_count)}
          hint={
            summary
              ? `${t("transactions.stats.conversionRate")} ${formatPercent(summary.conversion_rate, i18n.language)}`
              : undefined
          }
        />
        <KpiTile
          panel
          icon={Calculator}
          label={t("transactions.stats.averageCheck")}
          value={summary?.average_check != null ? money(summary.average_check) : none}
          trend={averageCheckTrend}
          hint={
            summary?.average_discount != null
              ? `${t("transactions.stats.averageDiscount")} ${formatPercent(summary.average_discount, i18n.language)}`
              : undefined
          }
        />
        <KpiTile
          panel
          icon={Wallet}
          label={t("transactions.stats.revenue")}
          value={summary ? money(summary.revenue) : none}
          trend={revenueTrend}
          hint={
            summary && Number(summary.refunded_amount) > 0
              ? `${t("transactions.stats.refunded")} ${money(summary.refunded_amount)}`
              : undefined
          }
        />
      </div>

      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <EmptyState text={t(hasFilters ? "transactions.noMatches" : "transactions.empty")} size="page" />
            )}
            {state.items.length > 0 && (
              <>
                <div className={LIST_SCROLL_X_CLASS}>
                  <div className="min-w-[850px]">
                    <div
                      className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}
                    >
                      <span className="col-span-2">{t("transactions.columns.order")}</span>
                      <span>{t("transactions.columns.purchaseType")}</span>
                      <span>{t("transactions.columns.amount")}</span>
                      <span>{t("transactions.columns.created")}</span>
                      <span>{t("transactions.columns.status")}</span>
                      <span />
                    </div>
                    <div className="flex flex-col gap-3">
                      {groups.map((group) => (
                        <section key={group.key} className="flex flex-col">
                          <h3>
                            <GroupToggle
                                  glass
                              open={!collapsedDays.has(group.key)}
                              onToggle={() => toggleDay(group.key)}
                              label={formatDayLabel(group.date, t, i18n.language)}
                              count={group.items.length}
                            />
                          </h3>
                          <Collapse open={!collapsedDays.has(group.key)} className={LIST_BODY_CLASS}>
                            {group.items.map((order) => {
                              const symbol = currencySymbol(order.currency);
                              const gatewayLabel = t(`settings.gateways.types.${order.gateway_type}` as ParseKeys);
                              // a free order never reached its gateway (old-version rows still name one)
                              const isFree = Number(order.final_price) === 0;

                              return (
                                <ListRow
                                  key={order.id}
                                  type="button"
                                  disabled={!canViewDetails}
                                  onClick={() => setDetailsOrder(order)}
                                  className={ROW_GRID_CLASSNAME}
                                >
                                  <IconCircle
                                    tone={PAYMENT_STATUS_BADGE_TONE[order.status]}
                                    glyph={<span className="text-sm font-bold">{symbol}</span>}
                                  />
                                  <span className="min-w-0">
                                    <span className="flex min-w-0 items-center gap-2">
                                      <span className="truncate text-sm font-medium text-foreground">
                                        {order.plan_snapshot.name}
                                        {" · "}
                                        {t("plans.daysShort", { count: order.duration_days })}
                                      </span>
                                      <span className="shrink-0 font-mono text-xs text-muted-foreground">
                                        #{order.id}
                                      </span>
                                    </span>
                                    <span className="flex min-w-0 gap-1 text-xs text-muted-foreground">
                                      <span className="truncate">
                                        {order.user ? userName(order.user, t) : t("users.deleted.name")}
                                      </span>
                                      <span className="shrink-0 font-mono">#{order.user_id}</span>
                                      {!isFree && <span className="shrink-0">&middot; {gatewayLabel}</span>}
                                    </span>
                                  </span>
                                  <span className="truncate text-sm text-foreground">
                                    {t(`transactions.purchaseType.${order.purchase_type}`)}
                                  </span>
                                  <span className="tabular-nums">
                                    <span className="block text-sm font-semibold text-foreground">
                                      {isFree
                                        ? t("transactions.free")
                                        : formatMoney(order.final_price, order.currency, i18n.language, true)}
                                    </span>
                                    {hasDiscount(order) && (
                                      <span className="block text-xs text-muted-foreground">
                                        <span className="line-through">
                                          {formatMoney(order.base_price, order.currency, i18n.language, true)}
                                        </span>{" "}
                                        <span className="text-primary">−{totalDiscountPercent(order)}%</span>
                                      </span>
                                    )}
                                  </span>
                                  <span className="text-sm tabular-nums text-foreground">
                                    {formatTime(order.created_at, i18n.language)}
                                  </span>
                                  <span>
                                    <Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>
                                      {t(`transactions.status.${order.status}`)}
                                    </Badge>
                                  </span>
                                  {canViewDetails ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                                </ListRow>
                              );
                            })}
                          </Collapse>
                        </section>
                      ))}
                    </div>
                  </div>
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
        </AnimatedHeight>
      </div>
      </div>
      </LoadGate>
      </div>

      {detailsOrder && (
        <TransactionDetailsDialog
          order={detailsOrder}
          onClose={() => setDetailsOrder(null)}
          onChanged={(changed) => {
            setState((prev) =>
              prev.kind === "ready"
                ? { ...prev, items: prev.items.map((item) => (item.id === changed.id ? changed : item)) }
                : prev,
            );
            reloadSummary();
            reloadCompare();
          }}
        />
      )}
    </div>
  );
}
