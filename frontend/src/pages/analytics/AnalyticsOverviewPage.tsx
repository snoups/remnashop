import { CreditCard, PieChart, ShoppingCart, TrendingDown, TrendingUp, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getAnalytics } from "@entities/analytics/api";
import type { Analytics, AnalyticsPeriodDays } from "@entities/analytics/api";
import { PeriodToggle } from "@shared/ui/PeriodToggle";
import { Spinner } from "@shared/ui/Spinner";
import { StatCard } from "@shared/ui/StatCard";

type AnalyticsState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Analytics };

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatRevenue(byCurrency: Record<string, string>): string {
  const entries = Object.entries(byCurrency).map(([currency, amount]) => `${amount} ${currency}`);
  return entries.length > 0 ? entries.join(", ") : "—";
}

export function AnalyticsOverviewPage() {
  const { t } = useTranslation();
  const [days, setDays] = useState<AnalyticsPeriodDays>(7);
  const [state, setState] = useState<AnalyticsState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    getAnalytics(days, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, [days]);

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex justify-end">
        <PeriodToggle value={days} onChange={setDays} />
      </div>

      {state.kind === "loading" && <Spinner className="py-12" />}
      {state.kind === "error" && (
        <div className="py-6 text-center text-sm text-error">{t("analytics.loadError")}</div>
      )}
      {state.kind === "ready" && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              icon={CreditCard}
              label={t("analytics.kpi.revenue")}
              value={formatRevenue(state.data.kpi.total_revenue_by_currency)}
            />
            <StatCard
              icon={TrendingUp}
              label={t("analytics.kpi.mrr")}
              value={`${state.data.kpi.mrr} ${state.data.kpi.report_currency}`}
            />
            <StatCard
              icon={PieChart}
              label={t("analytics.kpi.arpu")}
              value={`${state.data.kpi.arpu} ${state.data.kpi.report_currency}`}
            />
            <StatCard
              icon={Users}
              label={t("analytics.kpi.activeSubscriptions")}
              value={String(state.data.kpi.active_subscriptions)}
            />
            <StatCard
              icon={ShoppingCart}
              label={t("analytics.kpi.paidOrders")}
              value={String(state.data.kpi.paid_orders_count)}
            />
            <StatCard
              icon={UserCheck}
              label={t("analytics.kpi.conversionRate")}
              value={`${formatPercent(state.data.kpi.conversion_rate)} (${state.data.kpi.paid_in_period}/${state.data.kpi.registered_in_period})`}
            />
          </div>

          <div className="rounded-2xl border border-border bg-surface/40 p-4">
            <h3 className="mb-3 text-[13px] font-semibold text-foreground">{t("analytics.churn.title")}</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <StatCard
                icon={TrendingDown}
                label={t("analytics.churn.rate")}
                value={formatPercent(state.data.churn.churn_rate)}
              />
              <StatCard
                icon={TrendingUp}
                label={t("analytics.churn.retention")}
                value={formatPercent(state.data.churn.retention_rate)}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-[12px] text-muted-foreground">
              <span>
                {t("analytics.churn.prevActive")}: {state.data.churn.prev_active}
              </span>
              <span>
                {t("analytics.churn.stillActive")}: {state.data.churn.still_active}
              </span>
              <span>
                {t("analytics.churn.churned")}: {state.data.churn.churned}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
