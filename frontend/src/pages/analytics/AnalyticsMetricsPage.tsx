import { CreditCard, PieChart, TrendingUp, UserCheck, UserPlus, Users, RefreshCw, Gift } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getAnalytics } from "@entities/analytics/api";
import type { Analytics } from "@entities/analytics/api";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { CurrencyNote } from "@pages/analytics/charts";
import { rangeLabel, useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, ppTrend, relativeTrend } from "@pages/analytics/trends";

export function AnalyticsMetricsPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getAnalytics(period, signal), { deps: [period], keepData: true });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar currency={state.kind === "ready" ? state.data.report_currency : undefined} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && <Overview data={state.data} isAll={period.kind === "all"} />}
    </div>
  );
}

function Overview({ data, isAll }: { data: Analytics; isAll: boolean }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { current, previous, snapshot } = data;
  const currency = data.report_currency;
  const byCurrency = Object.entries(data.revenue_by_currency);
  const money = (value: string | number, exact = false) => formatMoney(value, currency, language, exact);
  const count = (value: number) => value.toLocaleString(language);

  const relative = (cur: string, prev: string, exact = false) =>
    isAll ? undefined : relativeTrend(Number(cur), Number(prev), money(prev, exact), t, language);

  const hasChurnBase = current.churn_base > 0;
  const churnPp = ppTrend(current.churn_rate, previous.churn_rate, t, language);
  // falling churn is the good direction
  const churnTrend = !isAll && hasChurnBase && previous.churn_base > 0 ? { ...churnPp, delta: -churnPp.delta } : undefined;

  const conversionDate = parseIsoDate(data.period.end.slice(0, 10));
  conversionDate?.setDate(conversionDate.getDate() - data.conversion_window_days);
  const conversionCaption = conversionDate
    ? t("analytics.metrics.conversionCaption", {
        date: new Intl.DateTimeFormat(language, { day: "numeric", month: "short" }).format(conversionDate),
      })
    : undefined;

  return (
    <>
      <p className={EYEBROW_CLASS}>
        {t("analytics.metrics.periodSection")}
        {!isAll &&
          ` · ${t("analytics.metrics.comparedWith", { range: rangeLabel(data.period.previous_start, data.period.previous_end, language) })}`}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <KpiTile
          highlighted
          icon={CreditCard}
          label={t("analytics.metrics.revenue")}
          value={money(current.revenue)}
          trend={relative(current.revenue, previous.revenue)}
          hint={
            byCurrency.length > 1 && (
              <span className="flex flex-wrap gap-1.5">
                {byCurrency.map(([code, amount]) => (
                  <Tag key={code}>{formatMoney(amount, code, language)}</Tag>
                ))}
              </span>
            )
          }
        />
        <KpiTile
          icon={PieChart}
          label={t("analytics.metrics.arppu")}
          value={money(current.arppu, true)}
          info={t("analytics.metrics.arppuHint")}
          trend={relative(current.arppu, previous.arppu, true)}
          hint={t("analytics.metrics.arppuCaption", { count: current.paying_users, formatted: count(current.paying_users) })}
        />
        <KpiTile
          icon={UserPlus}
          label={t("analytics.metrics.newPayers")}
          value={count(current.new_payers)}
          trend={isAll ? undefined : countTrend(current.new_payers, previous.new_payers, t, language)}
        />
        <KpiTile
          icon={UserCheck}
          label={t("analytics.metrics.conversion", { days: data.conversion_window_days })}
          value={formatPercent(current.conversion_rate, language)}
          info={t("analytics.metrics.conversionHint", { days: data.conversion_window_days })}
          trend={isAll ? undefined : ppTrend(current.conversion_rate, previous.conversion_rate, t, language)}
          hint={conversionCaption}
        />
        <KpiTile
          icon={RefreshCw}
          label={t("analytics.metrics.churn")}
          value={hasChurnBase ? formatPercent(current.churn_rate, language) : t("common.none")}
          info={t("analytics.metrics.churnHint")}
          trend={churnTrend}
          hint={hasChurnBase ? t("analytics.metrics.churnCaption", { churned: count(current.churned), base: count(current.churn_base) }) : undefined}
        />
      </div>

      <p className={EYEBROW_CLASS}>{t("analytics.metrics.nowSection")}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiTile
          icon={TrendingUp}
          label={t("analytics.metrics.mrr")}
          value={money(snapshot.mrr, true)}
          info={t("analytics.metrics.mrrHint")}
          hint={t("analytics.metrics.mrrCaption")}
        />
        <KpiTile
          icon={Users}
          label={t("analytics.metrics.paidSubscriptions")}
          value={count(snapshot.paid_subscriptions)}
          hint={t("analytics.metrics.limitedCaption", { value: count(snapshot.limited_subscriptions) })}
        />
        <KpiTile icon={Gift} label={t("analytics.metrics.trials")} value={count(snapshot.active_trials)} />
      </div>

      <CurrencyNote currency={currency} />
    </>
  );
}
