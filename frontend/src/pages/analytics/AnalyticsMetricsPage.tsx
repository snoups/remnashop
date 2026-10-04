import { CreditCard, PieChart, RefreshCw, ShoppingCart, TrendingUp, UserCheck, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formatMoney, formatPercent } from "@shared/lib/format";
import { getAnalytics } from "@entities/analytics/api";
import type { Analytics, AnalyticsPeriodDays } from "@entities/analytics/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { PeriodPills } from "@shared/ui/PeriodPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { CardHeader } from "@shared/ui/CardHeader";

export function AnalyticsMetricsPage() {
  const { t } = useTranslation();
  const [days, setDays] = useState<AnalyticsPeriodDays>(7);
  const [state] = useAsyncResource((signal) => getAnalytics(days, signal), { deps: [days] });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {state.kind === "ready" ? (
          <Tag>
            {t("analytics.reportCurrency")} · <span className="text-foreground">{state.data.report_currency}</span>
          </Tag>
        ) : (
          <span />
        )}
        <PeriodPills value={days} onChange={setDays} />
      </div>

      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <ErrorState text={t("analytics.loadError")} />
      )}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: Analytics }) {
  const { t, i18n } = useTranslation();
  const { current, snapshot } = data;
  const reportCurrency = data.report_currency;
  const revenue = Object.entries(data.revenue_by_currency);
  const retentionRate = 1 - current.churn_rate;
  const conversionPct = Math.min(100, current.conversion_rate * 100);
  const retentionPct = Math.min(100, retentionRate * 100);
  const hasChurnBase = current.churn_base > 0;

  return (
    <>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr_1fr]">
        <KpiTile
          icon={CreditCard}
          label={t("analytics.kpi.revenue")}
          value={formatMoney(current.revenue, reportCurrency, i18n.language)}
          hint={
            revenue.length > 1 && (
              <span className="flex flex-wrap gap-1.5">
                {revenue.map(([currency, amount]) => (
                  <Tag key={currency}>{formatMoney(amount, currency, i18n.language)}</Tag>
                ))}
              </span>
            )
          }
        />
        <KpiTile
          icon={TrendingUp}
          label={t("analytics.kpi.mrr")}
          value={formatMoney(snapshot.mrr, reportCurrency, i18n.language, true)}
          info={t("analytics.kpi.mrrHint")}
          hint={t("analytics.kpi.mrrCaption")}
        />
        <KpiTile
          icon={PieChart}
          label={t("analytics.kpi.arppu")}
          value={formatMoney(current.arppu, reportCurrency, i18n.language, true)}
          info={t("analytics.kpi.arppuHint")}
          hint={t("analytics.kpi.arppuCaption", { count: current.paying_users })}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiTile icon={Users} label={t("analytics.kpi.activeSubscriptions")} value={String(snapshot.paid_subscriptions)} />
        <KpiTile icon={ShoppingCart} label={t("analytics.kpi.paidOrders")} value={String(current.payments)} />
        <KpiTile
          icon={UserCheck}
          label={t("analytics.kpi.conversionRate", { days: data.conversion_window_days })}
          value={formatPercent(current.conversion_rate, i18n.language)}
          info={t("analytics.kpi.conversionRateHint", { days: data.conversion_window_days })}
          hint={
            <span className="flex items-center gap-3">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <span className="block h-full rounded-full bg-primary" style={{ width: `${conversionPct}%` }} />
              </span>
              {t("analytics.kpi.conversionOf", { paid: current.converted, total: current.conversion_cohort })}
            </span>
          }
        />
      </div>

      <Card>
        <CardHeader
          icon={RefreshCw}
          title={t("analytics.churn.title")}
          description={t("analytics.churn.titleHint")}
        />
        <div className="grid grid-cols-2 items-center gap-6 px-1 pb-1 pt-5 md:grid-cols-[180px_180px_minmax(0,1fr)]">
          <div>
            <p className="text-[12.5px] text-muted-foreground">{t("analytics.churn.retention")}</p>
            <p className="text-[28px] font-bold tabular-nums text-success">{hasChurnBase ? formatPercent(retentionRate, i18n.language) : "—"}</p>
          </div>
          <div>
            <p className="text-[12.5px] text-muted-foreground">{t("analytics.churn.rate")}</p>
            <p className="text-[28px] font-bold tabular-nums text-warning">{hasChurnBase ? formatPercent(current.churn_rate, i18n.language) : "—"}</p>
          </div>
          <div className="col-span-2 flex flex-col gap-2.5 md:col-span-1">
            <div className="flex h-2.5 gap-[3px] overflow-hidden rounded-full bg-white/[0.06]">
              {hasChurnBase && (
                <>
                  <div className="rounded-full bg-success" style={{ width: `${retentionPct}%` }} />
                  <div className="flex-1 rounded-full bg-warning" />
                </>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] tabular-nums text-muted-foreground">
              <LegendItem dotClassName="bg-muted-foreground" label={t("analytics.churn.prevActive")} value={current.churn_base} />
              <LegendItem dotClassName="bg-success" label={t("analytics.churn.stillActive")} value={current.churn_base - current.churned} />
              <LegendItem dotClassName="bg-warning" label={t("analytics.churn.churned")} value={current.churned} />
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

function LegendItem({ dotClassName, label, value }: { dotClassName: string; label: string; value: number }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`size-2 rounded-full ${dotClassName}`} />
      {label} · <span className="text-foreground">{value}</span>
    </span>
  );
}
