import { CreditCard, PieChart, RefreshCw, ShoppingCart, TrendingUp, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getAnalytics } from "@entities/analytics/api";
import type { Analytics, AnalyticsPeriodDays } from "@entities/analytics/api";
import { CURRENCY_SYMBOL } from "@entities/transactions/api";
import { AnalyticsCardHeader } from "@pages/analytics/AnalyticsCardHeader";
import { Card } from "@shared/ui/Card";
import { KpiTile } from "@shared/ui/KpiTile";
import { PeriodPills } from "@shared/ui/PeriodPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";

type AnalyticsState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Analytics };

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMoney(amount: string, currency: string, language: string): string {
  const value = new Intl.NumberFormat(language, { maximumFractionDigits: 2 }).format(Number(amount));
  return `${CURRENCY_SYMBOL[currency] ?? `${currency} `}${value}`;
}

export function AnalyticsMetricsPage() {
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        {state.kind === "ready" ? (
          <Tag>
            {t("analytics.reportCurrency")} · <span className="text-foreground">{state.data.kpi.report_currency}</span>
          </Tag>
        ) : (
          <span />
        )}
        <PeriodPills value={days} onChange={setDays} ariaLabel={t("dashboard.periodLabel")} />
      </div>

      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <div className="py-6 text-center text-sm text-error">{t("analytics.loadError")}</div>
      )}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: Analytics }) {
  const { t, i18n } = useTranslation();
  const { kpi, churn } = data;
  const reportCurrency = kpi.report_currency;
  const revenue = Object.entries(kpi.total_revenue_by_currency);
  const mainRevenue = kpi.total_revenue_by_currency[reportCurrency];
  const conversionPct = Math.min(100, kpi.conversion_rate * 100);
  const retentionPct = Math.min(100, churn.retention_rate * 100);

  return (
    <>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr_1fr]">
        <KpiTile
          icon={CreditCard}
          label={t("analytics.kpi.revenue")}
          value={mainRevenue !== undefined ? formatMoney(mainRevenue, reportCurrency, i18n.language) : "—"}
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
          value={formatMoney(kpi.mrr, reportCurrency, i18n.language)}
          info={t("analytics.kpi.mrrHint")}
          hint={t("analytics.kpi.mrrCaption")}
        />
        <KpiTile
          icon={PieChart}
          label={t("analytics.kpi.arpu")}
          value={formatMoney(kpi.arpu, reportCurrency, i18n.language)}
          info={t("analytics.kpi.arpuHint")}
          hint={t("analytics.kpi.arpuCaption")}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiTile icon={Users} label={t("analytics.kpi.activeSubscriptions")} value={String(kpi.active_subscriptions)} />
        <KpiTile icon={ShoppingCart} label={t("analytics.kpi.paidOrders")} value={String(kpi.paid_orders_count)} />
        <KpiTile
          icon={UserCheck}
          label={t("analytics.kpi.conversionRate")}
          value={formatPercent(kpi.conversion_rate)}
          info={t("analytics.kpi.conversionRateHint")}
          hint={
            <span className="flex items-center gap-3">
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <span className="block h-full rounded-full bg-primary" style={{ width: `${conversionPct}%` }} />
              </span>
              {t("analytics.kpi.conversionOf", { paid: kpi.paid_in_period, total: kpi.registered_in_period })}
            </span>
          }
        />
      </div>

      <Card>
        <AnalyticsCardHeader
          icon={RefreshCw}
          title={t("analytics.churn.title")}
          description={t("analytics.churn.titleHint")}
        />
        <div className="grid grid-cols-2 items-center gap-6 px-1 pb-1 pt-5 md:grid-cols-[180px_180px_minmax(0,1fr)]">
          <div>
            <p className="text-[12.5px] text-muted-foreground">{t("analytics.churn.retention")}</p>
            <p className="text-[28px] font-bold tabular-nums text-success">{formatPercent(churn.retention_rate)}</p>
          </div>
          <div>
            <p className="text-[12.5px] text-muted-foreground">{t("analytics.churn.rate")}</p>
            <p className="text-[28px] font-bold tabular-nums text-warning">{formatPercent(churn.churn_rate)}</p>
          </div>
          <div className="col-span-2 flex flex-col gap-2.5 md:col-span-1">
            <div className="flex h-2.5 gap-[3px] overflow-hidden rounded-full bg-white/[0.06]">
              {churn.prev_active > 0 && (
                <>
                  <div className="rounded-full bg-success" style={{ width: `${retentionPct}%` }} />
                  <div className="flex-1 rounded-full bg-warning" />
                </>
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] tabular-nums text-muted-foreground">
              <LegendItem dotClassName="bg-muted-foreground" label={t("analytics.churn.prevActive")} value={churn.prev_active} />
              <LegendItem dotClassName="bg-success" label={t("analytics.churn.stillActive")} value={churn.still_active} />
              <LegendItem dotClassName="bg-warning" label={t("analytics.churn.churned")} value={churn.churned} />
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
