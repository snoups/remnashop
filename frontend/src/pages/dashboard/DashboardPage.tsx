import { Layers, Users, Wallet, Wifi } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import {
  getHourlyOnline,
  getNodesOverview,
  getOverview,
} from "@entities/overview/api";
import type {
  HourlyOnline,
  NodesOverview,
  Overview,
} from "@entities/overview/api";
import { usePermissions } from "@entities/user/use-current-user";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { formatTime } from "@shared/lib/relative-time";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useRefreshSignal } from "@shared/lib/refresh-signal";
import { PAGE_CLASS, PAGE_SCROLL_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { AttentionCard } from "@pages/dashboard/AttentionCard";
import { ClientAppsCard } from "@pages/dashboard/ClientAppsCard";
import { FollowHeight, PAIR_ROW_CLASS } from "@pages/dashboard/FollowHeight";
import { NodesCard } from "@pages/dashboard/NodesCard";
import { OnlineCard } from "@pages/dashboard/OnlineCard";
import { RecentPaymentsCard } from "@pages/dashboard/RecentPaymentsCard";
import { RevenueCard } from "@pages/dashboard/RevenueCard";
import { SubscriptionsCard } from "@pages/dashboard/SubscriptionsCard";
import { SystemStatusCard } from "@pages/dashboard/SystemStatusCard";


function KpiRow({
  overview,
  hourlyOnline,
  nodes,
}: {
  overview: Overview;
  hourlyOnline: HourlyOnline | null;
  nodes: NodesOverview | null;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { users, subscriptions, revenue_today: revenue } = overview;
  const liveNodes = nodes?.available ? nodes.nodes.filter((node) => !node.is_disabled) : null;

  return (
    <div className="grid grid-cols-2 gap-5 md:grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
      {users && (
        <KpiTile
          panel
          icon={Users}
          label={t("dashboard.kpi.users")}
          value={users.total.toLocaleString(language)}
          hint={
            <>
              <span className={users.new_today > 0 ? "font-semibold text-success" : ""}>
                +{users.new_today.toLocaleString(language)}
              </span>{" "}
              {t("dashboard.kpi.today")}
            </>
          }
        />
      )}
      {subscriptions && (
        <KpiTile
          panel
          icon={Layers}
          label={t("dashboard.kpi.activePaid")}
          value={(subscriptions.paid_active + subscriptions.trials).toLocaleString(language)}
          hint={t("dashboard.kpi.trials", {
            count: subscriptions.trials,
            formatted: subscriptions.trials.toLocaleString(language),
          })}
        />
      )}
      {hourlyOnline && (
        <KpiTile
          panel
          icon={Wifi}
          label={t("dashboard.kpi.online")}
          value={hourlyOnline.current.toLocaleString(language)}
          hint={
            liveNodes && liveNodes.length > 0
              ? t("dashboard.kpi.onlineNodes", {
                  count: liveNodes.length,
                  connected: liveNodes.filter((node) => node.is_connected).length.toLocaleString(language),
                  total: liveNodes.length.toLocaleString(language),
                })
              : undefined
          }
        />
      )}
      {revenue && (
        <KpiTile
          panel
          icon={Wallet}
          label={t("dashboard.kpi.revenueToday")}
          value={formatMoney(revenue.today, revenue.report_currency, language)}
          hint={t("dashboard.kpi.revenueYesterday", {
            value: formatMoney(revenue.yesterday_same_time, revenue.report_currency, language),
          })}
          trend={
            revenue.change === null
              ? undefined
              : {
                  delta: revenue.change,
                  text: formatPercent(Math.abs(revenue.change), language),
                  hint: t("dashboard.kpi.revenueComparison"),
                }
          }
        />
      )}
    </div>
  );
}

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canViewNodes = permissions.includes("REMNAWAVE_NODES_VIEW");

  const { token: refreshKey, updatedAt, setUpdatedAt } = useRefreshSignal();
  // the header shows it beside the refresh button; gone with the page
  useEffect(() => () => setUpdatedAt(null), [setUpdatedAt]);
  const [kpiState] = useAsyncResource(getOverview, {
    deps: [refreshKey],
    keepData: true,
    onSuccess: () => setUpdatedAt(new Date()),
  });
  const [hourlyOnlineState] = useAsyncResource(getHourlyOnline, { deps: [refreshKey], keepData: true });
  const [nodesState] = useAsyncResource(
    (signal) => (canViewNodes ? getNodesOverview(signal) : Promise.resolve(null)),
    { deps: [refreshKey, canViewNodes], keepData: true },
  );
  const nodes = nodesState.kind === "ready" ? nodesState.data : null;
  const overview = kpiState.kind === "ready" ? kpiState.data : null;
  const subscriptions = overview?.subscriptions ?? null;
  const recentPayments = overview?.recent_payments ?? null;
  const showRevenue = permissions.includes("TRANSACTIONS_VIEW");
  const showClientApps = permissions.includes("REMNAWAVE_CLIENT_APPS_VIEW");

  return (
    <div data-fills-main data-under-header className={PAGE_CLASS}>
    <div className={PAGE_SCROLL_CLASS}>
    <LoadGate>
    <LoadGateHold
      isLoading={kpiState.kind === "loading" || hourlyOnlineState.kind === "loading" || nodesState.kind === "loading"}
    />
    <div className="flex flex-col gap-5">
      {updatedAt && (
        // the header holds it on desktop
        <span className="text-xs text-muted-foreground md:hidden">
          {t("dashboard.updatedAt", {
            time: formatTime(updatedAt, i18n.language),
          })}
        </span>
      )}
      {kpiState.kind === "loading" && <Spinner size="card" />}
      {kpiState.kind === "error" && (
        <div className="glass-panel rounded-3xl p-4">
          <ErrorState text={t("common.loadError")} />
        </div>
      )}
      {kpiState.kind === "ready" && (
        <KpiRow
          overview={kpiState.data}
          hourlyOnline={hourlyOnlineState.kind === "ready" ? hourlyOnlineState.data : null}
          nodes={nodes}
        />
      )}

      <AttentionCard refreshKey={refreshKey} />

      {(showRevenue || subscriptions) && (
        <div
          className={`grid grid-cols-1 gap-5 ${showRevenue && subscriptions ? "lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" : ""}`}
        >
          {showRevenue && <RevenueCard refreshKey={refreshKey} />}
          {subscriptions && <SubscriptionsCard subscriptions={subscriptions} />}
        </div>
      )}

      <div className={PAIR_ROW_CLASS}>
        <OnlineCard hourlyState={hourlyOnlineState} refreshKey={refreshKey} />
        {canViewNodes && (
          <FollowHeight>
            <NodesCard state={nodesState} />
          </FollowHeight>
        )}
      </div>

      {(showClientApps || recentPayments) && (
        <div className={PAIR_ROW_CLASS}>
          {showClientApps &&
            (recentPayments ? (
              <FollowHeight>
                <ClientAppsCard refreshKey={refreshKey} />
              </FollowHeight>
            ) : (
              <ClientAppsCard refreshKey={refreshKey} />
            ))}
          {recentPayments && <RecentPaymentsCard payments={recentPayments} revenue={overview?.revenue_today ?? null} />}
        </div>
      )}

      {kpiState.kind === "ready" && (
        <SystemStatusCard
          runtime={kpiState.data.runtime}
          memory={kpiState.data.host_memory}
          host={kpiState.data.host}
        />
      )}
    </div>
    </LoadGate>
    </div>
    </div>
  );
}
