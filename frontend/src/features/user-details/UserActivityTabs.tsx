import { Captions, CreditCard, Layers, Receipt, Share2, Ticket } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { ParseKeys, TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { PAYMENT_STATUS_BADGE_TONE, PURCHASE_TYPES, getTransactionSummary, listTransactions, listTransactionsAfter, type TransactionItem } from "@entities/transactions/api";
import { listUserPromocodeActivations, type UserPromocodeActivation } from "@entities/promocodes/api";
import { getUserReferralStats } from "@entities/referrals/api";
import { SUBSCRIPTION_STATUS_BADGE_TONE, listSubscriptions } from "@entities/subscriptions/api";
import { useAccountPermissions, usePermissions } from "@entities/user/use-current-user";
import { PaidTimeline } from "@features/user-details/PaidTimeline";
import { PURCHASE_TYPE_BAR_CLASS } from "@features/user-details/purchase-type";
import { TransactionDetailsDialog } from "@features/transaction-details/TransactionDetailsDialog";
import { InvitedUsersPage } from "@features/user-referrals/InvitedUsersList";
import { ReferralKpis } from "@features/user-referrals/ReferralOverview";
import { currencySymbol, formatMoney } from "@shared/lib/format";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { formatDate } from "@shared/lib/relative-time";
import { SECTION_TITLE_CLASS } from "@shared/ui/classes";

// Commerce tabs of the user details dialog: analytics, transactions, subscriptions, promocodes, referrals.

const TRANSACTIONS_PAGE_SIZE = 10;
// a user rarely has more; the tab shows the first page only
const SUBSCRIPTIONS_PAGE_SIZE = 10;
const PROMOCODES_PAGE_SIZE = 10;
// the backend's MAX_PAGE_SIZE
const ANALYTICS_ORDERS_LIMIT = 200;




// a KPI value: loading/forbidden/failed all read as a dash
function kpiValue<T>(state: AsyncState<T | null>, format: (data: T) => string, none: string): string {
  return state.kind === "ready" && state.data !== null ? format(state.data) : none;
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
  return <h3 className={SECTION_TITLE_CLASS}>{children}</h3>;
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
      <KpiTile glass
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
        <KpiTile glass
          label={t("users.details.analytics.saved")}
          value={saved}
          hint={t("users.details.analytics.savedHint", { count: discounted.length, total: paid.length })}
        />
      )}
      <KpiTile glass
        label={t("users.details.analytics.gateway")}
        value={topGateway ? t(`settings.gateways.types.${topGateway}` as ParseKeys) : t("common.none")}
        hint={topGateway ? t("users.details.analytics.gatewayHint", { count: topGatewayCount, total: paid.length }) : undefined}
      />
    </>
  );
}

export function AnalyticsTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const none = t("common.none");
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
  const money = (amount: string) => formatMoney(amount, data?.report_currency ?? "", i18n.language, true);
  const orderPage = orders.kind === "ready" ? orders.data : null;

  return (
    <div className="flex flex-col gap-3">
      {(canViewSummary || canViewOrders) && (
        <>
          <SectionTitle>
            <CreditCard className="size-3.5" />
            {t("users.details.analytics.purchases")}
          </SectionTitle>
          <div className="grid auto-rows-fr grid-cols-2 gap-3">
            {canViewSummary && (
              <KpiTile glass
                label={t("users.details.analytics.total")}
                value={kpiValue(summary, (s) => money(s.revenue), none)}
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
                  saved={canViewSummary ? kpiValue(summary, (s) => money(s.discount_amount), none) : undefined}
                />
              ) : orders.kind === "error" ? (
                <ErrorState text={t("common.loadError")} />
              ) : (
                <Spinner size="card" />
              ))}
          </div>
          {orderPage && <PaidTimeline orders={orderPage.items} />}
        </>
      )}
      {referrals.kind === "ready" && referrals.data && (
        <>
          <SectionTitle>
            <Share2 className="size-3.5" />
            {t("users.details.tabs.referrals")}
          </SectionTitle>
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
    (id: number, _page, signal, loaded?: TransactionItem[]) =>
      listTransactionsAfter({ userId: id, pageSize: TRANSACTIONS_PAGE_SIZE }, loaded, signal),
    userId,
  );
  const [openedOrder, setOpenedOrder] = useState<TransactionItem | null>(null);

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState icon={Receipt} text={t("users.details.empty.transactions")} />
      )}
      {state.kind === "ready" &&
        state.items.map((order) => {
          const symbol = currencySymbol(order.currency);
          return (
            <Row
              key={order.id}
              size="sm"
              glyph={<span className="text-[11px] font-bold">{symbol}</span>}
              tone={PAYMENT_STATUS_BADGE_TONE[order.status]}
              label={`${order.plan_snapshot.name} · ${t("plans.daysShort", { count: order.duration_days })}`}
              description={
                <>
                  {t(`transactions.purchaseType.${order.purchase_type}`)} · <span className="font-mono">#{order.id}</span> ·{" "}
                  <span className="font-mono">{formatDate(order.created_at, i18n.language)}</span>
                </>
              }
              onClick={canViewDetails ? () => setOpenedOrder(order) : undefined}
            >
              <span className="text-[13px] font-semibold tabular-nums text-foreground">
                {formatMoney(order.final_price, order.currency, i18n.language, true)}
              </span>
              <Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>{t(`transactions.status.${order.status}`)}</Badge>
            </Row>
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
    </DialogCard>
  );
}

export function SubscriptionsTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const permissions = useAccountPermissions(userId);
  const canOpen = permissions.includes("SUBSCRIPTIONS_DETAIL_VIEW");
  const { openSubscription } = useOpenEntity();
  const { state, isLoadingMore, hasMore, loadMore, reload } = usePaginatedList(
    (id: number, page, signal) => listSubscriptions({ userId: id, page, pageSize: SUBSCRIPTIONS_PAGE_SIZE }, signal),
    userId,
  );

  return (
    <>
      <DialogCard>
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState icon={Layers} text={t("users.details.empty.subscriptions")} />
        )}
        {state.kind === "ready" &&
          state.items.map((subscription) => (
            <Row
              key={subscription.id}
              size="sm"
              icon={Captions}
              tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}
              label={
                <>
                  <span className="truncate">{subscription.plan_snapshot.name}</span>
                  <span className="shrink-0 font-mono text-[12px] font-normal text-muted-foreground">#{subscription.id}</span>
                  {subscription.is_trial && (
                    <Badge tone="warning">
                      {t("subscriptions.trial")}
                    </Badge>
                  )}
                </>
              }
              description={`${
                subscription.effective_traffic_limit === 0
                  ? t("subscriptions.trafficUnlimited")
                  : `${subscription.effective_traffic_limit} GB`
              } · ${
                subscription.effective_device_limit === 0
                  ? t("subscriptions.devicesUnlimited")
                  : t("subscriptions.devicesCount", { count: subscription.effective_device_limit })
              }`}
              onClick={canOpen ? () => openSubscription(subscription.id, { data: subscription, onChanged: reload }) : undefined}
            >
              {subscription.status !== "DELETED" && (
                <span className="text-[12.5px] tabular-nums text-muted-foreground">
                  {t("subscriptions.until", { date: formatDate(subscription.expire_at, i18n.language) })}
                </span>
              )}
              <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}>
                {t(`subscriptions.status.${subscription.status}`)}
              </Badge>
            </Row>
          ))}
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
      </DialogCard>
    </>
  );
}

export function PromocodesTab({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const canOpen = usePermissions().includes("PROMOCODES_DETAIL_VIEW");
  const { openPromocode } = useOpenEntity();
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, page, signal) => listUserPromocodeActivations(id, page, PROMOCODES_PAGE_SIZE, signal),
    userId,
  );

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState icon={Ticket} text={t("users.details.empty.promocodes")} />
      )}
      {state.kind === "ready" &&
        state.items.map((activation) => (
          <Row
            key={activation.activation_id}
            size="sm"
            icon={Ticket}
            label={<span className="truncate font-mono">{activation.code}</span>}
            description={<span className="font-mono">{formatDate(activation.activated_at, i18n.language)}</span>}
            onClick={canOpen ? () => openPromocode(activation.promocode_id) : undefined}
          >
            <Tag>{activationReward(activation, t)}</Tag>
          </Row>
        ))}
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
    </DialogCard>
  );
}

export function InvitedTab({ userId }: { userId: number }) {
  return <InvitedUsersPage userId={userId} />;
}
