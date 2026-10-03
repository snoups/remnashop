import { AlertCircle, CreditCard, Receipt, Ticket } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { ParseKeys, TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { PAYMENT_STATUS_BADGE_TONE, PURCHASE_TYPES, getTransactionSummary, listTransactions, type TransactionItem } from "@entities/transactions/api";
import { listUserPromocodeActivations, type UserPromocodeActivation } from "@entities/promocodes/api";
import { getUserReferralStats } from "@entities/referrals/api";
import { SUBSCRIPTION_STATUS_BADGE_TONE, listSubscriptions } from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { PaidTimeline } from "@features/user-details/PaidTimeline";
import { PURCHASE_TYPE_BAR_CLASS } from "@features/user-details/purchase-type";
import { TransactionDetailsDialog } from "@features/transaction-details/TransactionDetailsDialog";
import { ReferralManagePanel } from "@features/user-referrals/ReferralManagePanel";
import { ReferralKpis, ReferralProgramCard } from "@features/user-referrals/ReferralOverview";
import { ResetReferralCodeButton } from "@features/user-referrals/ResetReferralCodeButton";
import { currencySymbol, formatMoney } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EmptyState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { formatDate } from "@shared/lib/relative-time";

// Commerce tabs of the user details dialog: analytics, transactions, subscriptions, promocodes, referrals.

const TRANSACTIONS_PAGE_SIZE = 10;
// a user rarely has more; the tab shows the first page only
const SUBSCRIPTIONS_PAGE_SIZE = 50;
// the backend's MAX_PAGE_SIZE
const ANALYTICS_ORDERS_LIMIT = 200;


const ROW_CLASSNAME = "flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left";
const ROW_ICON_CLASSNAME =
  "flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-semibold text-foreground";

function LoadError({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-error">
      <AlertCircle className="size-5" />
      <p className="text-sm">{text}</p>
    </div>
  );
}


// a KPI value: loading/forbidden/failed all read as a dash
function kpiValue<T>(state: AsyncState<T | null>, format: (data: T) => string): string {
  return state.kind === "ready" && state.data !== null ? format(state.data) : "—";
}

// the same "+30 дн." / "-10%" the promocode dialog shows; the rest has no number worth a tag
function activationReward(activation: UserPromocodeActivation, t: TFunction): string {
  if (activation.reward === null) return t(`promocodes.rewardTypeShort.${activation.reward_type}`);
  if (activation.reward_type === "DURATION") return `+${t("plans.daysShort", { count: activation.reward })}`;
  if (activation.reward_type === "PERSONAL_DISCOUNT" || activation.reward_type === "PURCHASE_DISCOUNT") {
    return `-${activation.reward}%`;
  }
  return `${t(`promocodes.rewardTypeShort.${activation.reward_type}`)} · ${activation.reward}`;
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="px-0.5 pt-1 text-[11px] font-semibold uppercase tracking-wide text-foreground">{children}</h3>;
}

// `saved` comes from the summary, already in the report currency; undefined hides the tile
function PurchaseKpis({ orders, total, saved }: { orders: TransactionItem[]; total: number; saved?: string }) {
  const { t } = useTranslation();
  const paid = orders.filter((order) => order.status === "PAID");
  const byType = PURCHASE_TYPES.map((type) => ({ type, count: paid.filter((o) => o.purchase_type === type).length })).filter(
    ({ count }) => count > 0,
  );
  const discounted = paid.filter((order) => Number(order.base_price) > Number(order.final_price));
  const gatewayCounts = new Map<string, number>();
  for (const order of paid) gatewayCounts.set(order.gateway_type, (gatewayCounts.get(order.gateway_type) ?? 0) + 1);
  const [topGateway, topGatewayCount] = [...gatewayCounts].sort((a, b) => b[1] - a[1])[0] ?? [];

  return (
    <>
      <KpiTile
        label={t("users.details.analytics.paid")}
        value={String(paid.length)}
        valueSuffix={t("users.details.analytics.ofTotal", { total })}
        hint={
          byType.length > 0 && (
            <span className="flex flex-col gap-1.5">
              <span className="flex h-1.5 gap-0.5 overflow-hidden rounded-full">
                {byType.map(({ type, count }) => (
                  <span key={type} className={PURCHASE_TYPE_BAR_CLASS[type]} style={{ flexGrow: count }} />
                ))}
              </span>
              <span className="flex flex-wrap gap-x-3 gap-y-0.5">
                {byType.map(({ type, count }) => (
                  <span key={type} className="flex items-center gap-1.5">
                    <span className={`size-2 rounded-full ${PURCHASE_TYPE_BAR_CLASS[type]}`} />
                    <span className="font-semibold text-foreground">{count}</span>
                    {t(`users.details.analytics.purchaseType.${type}`, { count })}
                  </span>
                ))}
              </span>
            </span>
          )
        }
      />
      {saved !== undefined && (
        <KpiTile
          label={t("users.details.analytics.saved")}
          value={saved}
          hint={t("users.details.analytics.savedHint", { count: discounted.length, total: paid.length })}
        />
      )}
      <KpiTile
        label={t("users.details.analytics.gateway")}
        value={topGateway ? t(`settings.gateways.types.${topGateway}` as ParseKeys) : "—"}
        hint={topGateway ? t("users.details.analytics.gatewayHint", { count: topGatewayCount, total: paid.length }) : undefined}
      />
    </>
  );
}

export function AnalyticsTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canViewSummary = permissions.includes("TRANSACTIONS_SUMMARY_VIEW");
  const canViewOrders = permissions.includes("TRANSACTIONS_VIEW");
  const [summary] = useAsyncResource((signal) =>
    canViewSummary ? getTransactionSummary({ userId }, signal) : Promise.resolve(null),
  );
  // first ANALYTICS_ORDERS_LIMIT orders only; a per-user aggregate endpoint once someone has more
  const [orders] = useAsyncResource((signal) =>
    canViewOrders ? listTransactions({ userId, pageSize: ANALYTICS_ORDERS_LIMIT }, signal) : Promise.resolve(null),
  );
  const [referrals] = useAsyncResource((signal) =>
    permissions.includes("REFERRALS_VIEW") ? getUserReferralStats(userId, signal) : Promise.resolve(null),
  );

  const data = summary.kind === "ready" ? summary.data : null;
  const money = (amount: string) => formatMoney(amount, data?.report_currency ?? "", i18n.language);
  const orderPage = orders.kind === "ready" ? orders.data : null;

  return (
    <div className="flex flex-col gap-3">
      {(canViewSummary || canViewOrders) && (
        <>
          <SectionTitle>{t("users.details.analytics.purchases")}</SectionTitle>
          <div className="grid grid-cols-2 gap-3">
            {canViewSummary && (
              <KpiTile
                label={t("users.details.analytics.total")}
                value={kpiValue(summary, (s) => money(s.revenue))}
                hint={
                  data && Number(data.refunded_amount) > 0
                    ? `${t("transactions.stats.refunded")} ${money(data.refunded_amount)}`
                    : undefined
                }
              />
            )}
            {canViewOrders &&
              (orderPage ? (
                <PurchaseKpis
                  orders={orderPage.items}
                  total={orderPage.total}
                  saved={canViewSummary ? kpiValue(summary, (s) => money(s.discount_amount)) : undefined}
                />
              ) : orders.kind === "error" ? (
                <LoadError text={t("transactions.loadError")} />
              ) : (
                <Spinner size="card" />
              ))}
          </div>
          {orderPage && <PaidTimeline orders={orderPage.items} />}
        </>
      )}
      {referrals.kind === "ready" && referrals.data && (
        <>
          <SectionTitle>{t("users.details.tabs.referrals")}</SectionTitle>
          <ReferralKpis userId={userId} stats={referrals.data} />
        </>
      )}
    </div>
  );
}

export function TransactionsTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const canViewDetails = usePermissions().includes("TRANSACTIONS_DETAIL_VIEW");
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, page, signal) => listTransactions({ userId: id, page, pageSize: TRANSACTIONS_PAGE_SIZE }, signal),
    userId,
  );
  const [openedOrder, setOpenedOrder] = useState<TransactionItem | null>(null);

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <LoadError text={t("transactions.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState icon={Receipt} text={t("users.details.empty.transactions")} />
      )}
      {state.kind === "ready" &&
        state.items.map((order) => {
          const symbol = currencySymbol(order.currency);
          return (
            <motion.button
              key={order.id}
              type="button"
              disabled={!canViewDetails}
              onClick={() => setOpenedOrder(order)}
              {...(canViewDetails && bounceTap(0.03))}
              className={`${ROW_CLASSNAME} transition-colors enabled:hover:bg-white/[0.04] disabled:cursor-default`}
            >
              <span className={ROW_ICON_CLASSNAME}>
                {symbol}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-[13px] font-medium text-foreground/90">
                    {order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? "—"}
                    {" · "}
                    {t("plans.daysShort", { count: order.duration_days })}
                  </span>
                </span>
                <span className="block truncate text-[12px] text-muted-foreground">
                  {t(`transactions.purchaseType.${order.purchase_type}`)} · <span className="font-mono">#{order.id}</span> ·{" "}
                  <span className="font-mono">{formatDate(order.created_at, i18n.language)}</span>
                </span>
              </span>
              <span className="shrink-0 text-[13.5px] font-semibold tabular-nums text-foreground">
                {formatMoney(order.final_price, order.currency, i18n.language, true)}
              </span>
              <Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>{t(`transactions.status.${order.status}`)}</Badge>
            </motion.button>
          );
        })}
      {state.kind === "ready" && hasMore && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void loadMore()}
            isLoading={isLoadingMore}
            shown={state.items.length}
            total={state.total}
          />
        </div>
      )}
      {openedOrder && <TransactionDetailsDialog order={openedOrder} onClose={() => setOpenedOrder(null)} />}
    </Card>
  );
}

export function SubscriptionsTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource((signal) =>
    listSubscriptions({ userId, pageSize: SUBSCRIPTIONS_PAGE_SIZE }, signal),
  );

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <LoadError text={t("subscriptions.loadError")} />}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <EmptyState icon={CreditCard} text={t("users.details.empty.subscriptions")} />
      )}
      {state.kind === "ready" &&
        state.data.items.map((subscription) => (
          <div key={subscription.id} className={ROW_CLASSNAME}>
            <span className={ROW_ICON_CLASSNAME}>
              <CreditCard className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex min-w-0 items-center gap-2">
                <span className="truncate text-[13px] font-medium text-foreground/90">
                  {subscription.tag ?? `#${subscription.id}`}
                </span>
                {subscription.is_trial && <Tag>{t("subscriptions.trial")}</Tag>}
              </span>
              <span className="block truncate text-[12px] text-muted-foreground">
                {subscription.effective_traffic_limit === 0
                  ? t("subscriptions.trafficUnlimited")
                  : `${subscription.effective_traffic_limit} GB`}
                {" · "}
                {subscription.effective_device_limit === 0
                  ? t("subscriptions.devicesUnlimited")
                  : t("subscriptions.devicesCount", { count: subscription.effective_device_limit })}
              </span>
            </span>
            <span className="shrink-0 text-[12.5px] tabular-nums text-muted-foreground">
              {formatDate(subscription.expire_at, i18n.language)}
            </span>
            <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}>
              {t(`subscriptions.status.${subscription.status}`)}
            </Badge>
          </div>
        ))}
    </Card>
  );
}

export function PromocodesTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource((signal) => listUserPromocodeActivations(userId, signal));

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <LoadError text={t("promocodes.loadError")} />}
      {state.kind === "ready" && state.data.length === 0 && (
        <EmptyState icon={Ticket} text={t("users.details.empty.promocodes")} />
      )}
      {state.kind === "ready" &&
        state.data.map((activation) => (
          <div key={activation.activation_id} className={ROW_CLASSNAME}>
            <span className={ROW_ICON_CLASSNAME}>
              <Ticket className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-medium text-foreground/90">
              {activation.code}
            </span>
            <Tag>{activationReward(activation, t)}</Tag>
            <span className="shrink-0 text-[12.5px] tabular-nums text-muted-foreground">
              {formatDate(activation.activated_at, i18n.language)}
            </span>
          </div>
        ))}
    </Card>
  );
}

export function ReferralsTab({ userId, readOnly = false }: { userId: number; readOnly?: boolean }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canAdjustPoints = !readOnly && permissions.includes("REFERRALS_POINTS_MANAGE");
  const canResetCode = !readOnly && permissions.includes("REFERRALS_CODE_RESET");
  const [state, , setData] = useAsyncResource((signal) => getUserReferralStats(userId, signal));

  if (state.kind === "loading") return <Spinner size="card" />;
  if (state.kind === "error") return <LoadError text={t("referrals.stats.loadError")} />;
  return (
    <div className="flex flex-col gap-3">
      {/* the manage panel below carries the code itself */}
      <ReferralProgramCard stats={state.data} showCode={!(canAdjustPoints || canResetCode)} />
      {(canAdjustPoints || canResetCode) && (
        <ReferralManagePanel userId={userId} stats={state.data} canAdjustPoints={canAdjustPoints} onChanged={setData} />
      )}
      {canResetCode && state.data.referral_code && (
        <ResetReferralCodeButton userId={userId} onReset={setData} className="w-full" />
      )}
    </div>
  );
}
