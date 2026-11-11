import {
  CalendarClock,
  Coins,
  CreditCard,
  Gift,
  Layers,
  PlugZap,
  RefreshCw,
  TrendingUp,
  UserCheck,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { getAnalytics } from "@entities/analytics/api";
import type { Analytics } from "@entities/analytics/api";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { CurrencyNote } from "@pages/analytics/charts";
import { rangeLabel, useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, ppTrend, previousPeriodHint, relativeTrend } from "@pages/analytics/trends";

export function AnalyticsMetricsPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getAnalytics(period, signal), { deps: [period], keepData: true });

  return (
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && <Overview data={state.data} isAll={period.kind === "all"} />}
    </div>
  );
}

function Overview({ data, isAll }: { data: Analytics; isAll: boolean }) {
  const { t, i18n } = useTranslation();
  const vs = previousPeriodHint(useAnalyticsPeriod().period, t);
  const language = i18n.language;
  const { current, previous, snapshot } = data;
  const currency = data.report_currency;
  const byCurrency = Object.entries(data.revenue_by_currency);
  const money = (value: string | number, exact = false) => formatMoney(value, currency, language, exact);
  const count = (value: number) => value.toLocaleString(language);

  const relative = (cur: string, prev: string) =>
    isAll ? undefined : relativeTrend(Number(cur), Number(prev), vs, language);

  const hasChurnBase = current.churn_base > 0;
  const churnPp = ppTrend(current.churn_rate, previous.churn_rate, vs, t, language);
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
      <div className="grid grid-cols-2 gap-5 xl:grid-cols-4">
        <KpiTile
          panel
          icon={CreditCard}
          label={t("analytics.metrics.revenue")}
          value={money(current.revenue)}
          trend={relative(current.revenue, previous.revenue)}
          hint={
            (current.paying_users > 0 || byCurrency.length > 1) && (
              <span className="flex flex-col gap-1.5">
                {current.paying_users > 0 &&
                  t("analytics.metrics.revenueCaption", {
                    payers: count(current.paying_users),
                    arppu: money(current.arppu, true),
                  })}
                {byCurrency.length > 1 && (
                  <span className="flex flex-wrap gap-1.5">
                    {byCurrency.map(([code, amount]) => (
                      <Tag key={code}>{formatMoney(amount, code, language)}</Tag>
                    ))}
                  </span>
                )}
              </span>
            )
          }
        />
        <KpiTile
          panel
          icon={UserPlus}
          label={t("analytics.metrics.newPayers")}
          value={count(current.new_payers)}
          trend={isAll ? undefined : countTrend(current.new_payers, previous.new_payers, vs, language)}
        />
        <KpiTile
          panel
          icon={UserCheck}
          label={t("analytics.metrics.conversion", { days: data.conversion_window_days })}
          value={current.conversion_cohort > 0 ? formatPercent(current.conversion_rate, language) : t("common.none")}
          info={t("analytics.metrics.conversionHint", { days: data.conversion_window_days })}
          trend={
            // a rate with no one behind it, now or before, isn't a change
            isAll || current.conversion_cohort === 0 || previous.conversion_cohort === 0
              ? undefined
              : ppTrend(current.conversion_rate, previous.conversion_rate, vs, t, language)
          }
          hint={conversionCaption}
        />
        <KpiTile
          panel
          icon={RefreshCw}
          label={t("analytics.metrics.churn")}
          value={hasChurnBase ? formatPercent(current.churn_rate, language) : t("common.none")}
          info={t("analytics.metrics.churnHint")}
          trend={churnTrend}
          hint={hasChurnBase ? t("analytics.metrics.churnCaption", { churned: count(current.churned), base: count(current.churn_base) }) : undefined}
        />
      </div>

      <p className={EYEBROW_CLASS}>{t("analytics.metrics.nowSection")}</p>
      <div className="grid grid-cols-2 gap-5 xl:grid-cols-4">
        <KpiTile
          panel
          icon={TrendingUp}
          label={t("analytics.metrics.mrr")}
          value={money(snapshot.mrr, true)}
          info={t("analytics.metrics.mrrHint")}
          hint={t("analytics.metrics.mrrCaption")}
        />
        <KpiTile
          panel
          icon={Wallet}
          label={t("analytics.metrics.arpu")}
          value={
            snapshot.paying_customers > 0
              ? money(Number(snapshot.mrr) / snapshot.paying_customers, true)
              : t("common.none")
          }
          info={t("analytics.metrics.arpuHint")}
        />
        <KpiTile
          panel
          icon={Users}
          label={t("analytics.metrics.payingCustomers")}
          value={count(snapshot.paying_customers)}
          hint={t("analytics.metrics.payingCustomersCaption")}
        />
        <KpiTile
          panel
          icon={Layers}
          label={t("analytics.metrics.paidSubscriptions")}
          value={count(snapshot.paid_subscriptions)}
          hint={t("analytics.metrics.limitedCaption", { value: count(snapshot.limited_subscriptions) })}
        />
        <KpiTile
          panel
          icon={PlugZap}
          label={t("analytics.metrics.neverConnected")}
          value={count(snapshot.never_connected)}
          hint={t("analytics.metrics.neverConnectedCaption")}
        />
        <KpiTile
          panel
          icon={CalendarClock}
          label={t("analytics.metrics.expiringSoon", { count: snapshot.expiring_soon_days })}
          value={count(snapshot.expiring_soon)}
          hint={t("analytics.metrics.expiringSoonCaption", { money: money(snapshot.expiring_soon_mrr) })}
        />
        <KpiTile
          panel
          icon={Gift}
          label={t("analytics.metrics.trials")}
          value={count(snapshot.active_trials)}
          hint={t("analytics.metrics.trialsEndingCaption", {
            count: snapshot.trials_ending_days,
            value: count(snapshot.trials_ending_soon),
          })}
        />
        <KpiTile
          panel
          icon={Coins}
          label={t("analytics.metrics.balances")}
          value={t("analytics.metrics.pointsValue", {
            count: Number(snapshot.points_owed),
            formatted: count(Number(snapshot.points_owed)),
          })}
          hint={t("analytics.metrics.bonusDaysCaption", {
            count: snapshot.bonus_days_owed,
            formatted: count(snapshot.bonus_days_owed),
          })}
        />
      </div>

      <CurrencyNote currency={currency} />
    </>
  );
}
