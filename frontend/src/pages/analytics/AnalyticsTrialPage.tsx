import type { ParseKeys } from "i18next";
import { BarChart3, CalendarClock, Clock, Package, Receipt, Timer, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getTrial } from "@entities/analytics/api";
import type { Trial } from "@entities/analytics/api";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Section } from "@shared/ui/glass/Section";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { BarRows, ColumnChart, Legend } from "@pages/analytics/charts";
import type { BarRow, Column } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, ppTrend, previousPeriodHint, relativeTrend } from "@pages/analytics/trends";

const AFTER_PREFIX = "after_";

export function AnalyticsTrialPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getTrial(period, signal), { deps: [period], keepData: true });

  return (
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && <Overview data={state.data} isAll={period.kind === "all"} />}
    </div>
  );
}

function Overview({ data, isAll }: { data: Trial; isAll: boolean }) {
  const { t, i18n } = useTranslation();
  const vs = previousPeriodHint(useAnalyticsPeriod().period, t);
  const language = i18n.language;
  const currency = data.report_currency;

  const count = (value: number) => value.toLocaleString(language);
  const conversionTrend =
    isAll || data.trials === 0 || data.previous_conversion_rate === null
      ? undefined
      : ppTrend(data.conversion_rate, data.previous_conversion_rate, vs, t, language);

  const isAfter = (key: string) => key.startsWith(AFTER_PREFIX);
  const dayTotal = data.by_trial_day.reduce((sum, bucket) => sum + bucket.count, 0);
  const afterTotal = data.by_trial_day.filter((bucket) => isAfter(bucket.key)).reduce((sum, bucket) => sum + bucket.count, 0);
  const lastDay = data.by_trial_day.find((bucket) => bucket.key === String(data.trial_days));
  const share = (value: number) => formatPercent(dayTotal > 0 ? value / dayTotal : 0, language);

  const dayColumns: Column[] = data.by_trial_day.map((bucket) => ({
    key: bucket.key,
    // a long trial groups its days: "8_14" is days 8 to 14
    label: isAfter(bucket.key) ? t(`analytics.trial.after.${bucket.key}` as ParseKeys) : bucket.key.replace("_", "–"),
    segments: [{ value: bucket.count, className: isAfter(bucket.key) ? "bg-success" : "bg-primary" }],
    caption: count(bucket.count),
  }));

  const viaTotal = data.time_to_first_payment.reduce((sum, bucket) => sum + bucket.via_trial, 0);
  const directTotal = data.time_to_first_payment.reduce((sum, bucket) => sum + bucket.direct, 0);
  const payColumns: Column[] = data.time_to_first_payment.map((bucket) => ({
    key: bucket.key,
    label: t(`analytics.trial.timeToPay.${bucket.key}` as ParseKeys),
    segments: [
      { value: bucket.via_trial, className: "bg-primary" },
      { value: bucket.direct, className: "bg-warning" },
    ],
    caption: count(bucket.via_trial + bucket.direct),
  }));

  const planPayments = data.plans_after_trial.reduce((sum, group) => sum + group.payments, 0);
  const planRows: BarRow[] = data.plans_after_trial.map((group) => ({
    key: group.key,
    label: group.key,
    value: group.payments,
    cells: [count(group.payments), formatPercent(planPayments > 0 ? group.payments / planPayments : 0, language)],
  }));

  return (
    <>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          panel
          icon={Timer}
          label={t("analytics.trial.trials")}
          value={count(data.trials)}
          trend={isAll ? undefined : countTrend(data.trials, data.previous_trials, vs, language)}
        />
        <KpiTile
          panel
          icon={CalendarClock}
          label={t("analytics.trial.conversion")}
          value={data.trials > 0 ? formatPercent(data.conversion_rate, language) : t("common.none")}
          trend={conversionTrend}
          hint={data.trials > 0 ? t("analytics.trial.convertedCaption", { converted: count(data.converted), trials: count(data.trials) }) : undefined}
        />
        <KpiTile
          panel
          icon={Wallet}
          label={t("analytics.trial.revenue")}
          info={t("analytics.trial.revenueInfo")}
          value={formatMoney(data.revenue_from_converted, currency, language)}
          trend={
            isAll
              ? undefined
              : relativeTrend(Number(data.revenue_from_converted), Number(data.previous_revenue_from_converted), vs, language)
          }
        />
        <KpiTile
          panel
          icon={Clock}
          label={t("analytics.trial.daysToPay")}
          // 0 is a same-day payment once someone has paid
          value={data.converted > 0 ? data.median_days_to_pay.toLocaleString(language) : t("common.none")}
          hint={t("analytics.trial.daysToPayCaption")}
        />
      </div>

      <Section
        icon={Receipt}
        title={t("analytics.trial.timeToPayTitle")}
        description={t("analytics.trial.timeToPayDescription")}
      >
        <div className="flex flex-col gap-4 px-3.5 pt-4">
          <ColumnChart columns={payColumns} empty={t("analytics.emptyPeriod")} />
          <Legend
            items={[
              { className: "bg-primary", label: t("analytics.trial.viaTrial", { value: count(viaTotal) }) },
              { className: "bg-warning", label: t("analytics.trial.noTrial", { value: count(directTotal) }) },
            ]}
          />
        </div>
      </Section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section
          stretched
          icon={BarChart3}
          title={t("analytics.trial.byDayTitle")}
          description={t("analytics.trial.byDayDescription")}
        >
          <div className="flex flex-col gap-4 px-3.5 pt-4">
            <ColumnChart columns={dayColumns} empty={t("analytics.emptyPeriod")} />
            <Legend
              items={[
                { className: "bg-primary", label: t("analytics.trial.during") },
                { className: "bg-success", label: t("analytics.trial.afterEnd") },
              ]}
            />
            {dayTotal > 0 && (
              <div className="flex flex-wrap gap-2">
                <Tag>{t("analytics.trial.lastDay", { share: share(lastDay?.count ?? 0) })}</Tag>
                <Tag>{t("analytics.trial.afterEndShare", { share: share(afterTotal) })}</Tag>
              </div>
            )}
          </div>
        </Section>
        <Section
          stretched
          icon={Package}
          title={t("analytics.trial.plansTitle")}
          description={t("analytics.trial.plansDescription")}
        >
          <BarRows compact rows={planRows} empty={t("analytics.emptyPeriod")} />
        </Section>
      </div>

    </>
  );
}
