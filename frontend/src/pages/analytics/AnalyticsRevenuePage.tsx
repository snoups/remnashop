import { BarChart3, CreditCard, Receipt, RotateCcw, ShoppingCart } from "lucide-react";
import type { ParseKeys } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getRevenue } from "@entities/analytics/api";
import type { AnalyticsPeriod, GatewayStats, Revenue, RevenueGranularity, RevenueGroup } from "@entities/analytics/api";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { BarRows, ColumnChart, CurrencyNote, Legend } from "@pages/analytics/charts";
import type { BarRow } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, relativeTrend } from "@pages/analytics/trends";

const GRANULARITIES: RevenueGranularity[] = ["day", "week", "month"];
const DAY_MS = 86_400_000;
const MAX_DAILY_RANGE_DAYS = 92;

function defaultGranularity(period: AnalyticsPeriod): RevenueGranularity {
  if (period.kind === "all") return "month";
  if (period.kind === "days") return period.days <= 30 ? "day" : period.days === 90 ? "week" : "month";
  const from = parseIsoDate(period.from);
  const to = parseIsoDate(period.to);
  return from && to && (to.getTime() - from.getTime()) / DAY_MS > MAX_DAILY_RANGE_DAYS ? "month" : "day";
}

export function AnalyticsRevenuePage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  // a manual pick holds only for the period it was made in
  const [manual, setManual] = useState<{ period: AnalyticsPeriod; granularity: RevenueGranularity } | null>(null);
  const granularity = manual?.period === period ? manual.granularity : defaultGranularity(period);
  const [state] = useAsyncResource((signal) => getRevenue(period, granularity, signal), {
    deps: [period, granularity],
    keepData: true,
  });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar currency={state.kind === "ready" ? state.data.report_currency : undefined} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <Overview data={state.data} isAll={period.kind === "all"} granularity={granularity} onGranularity={(value) => setManual({ period, granularity: value })} />
      )}
    </div>
  );
}

function Overview({
  data,
  isAll,
  granularity,
  onGranularity,
}: {
  data: Revenue;
  isAll: boolean;
  granularity: RevenueGranularity;
  onGranularity: (value: RevenueGranularity) => void;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const { totals } = data;
  const money = (value: string | number, exact = false) => formatMoney(value, currency, language, exact);
  const revenue = Number(totals.revenue);
  const sharePct = (value: number) => formatPercent(revenue > 0 ? value / revenue : 0, language);

  const count = (value: number) => value.toLocaleString(language);
  const revenueTrend = isAll
    ? undefined
    : relativeTrend(revenue, Number(totals.previous_revenue), money(totals.previous_revenue), t, language);
  const paymentsTrend = isAll ? undefined : countTrend(totals.payments, totals.previous_payments, t, language);

  const labelFormat = new Intl.DateTimeFormat(
    language,
    granularity === "month" ? { month: "short" } : { day: "numeric", month: "short" },
  );
  const columns = data.series.map((bucket) => {
    const start = parseIsoDate(bucket.start.slice(0, 10));
    return {
      key: bucket.start,
      label: start ? labelFormat.format(start) : "",
      segments: [
        { value: Number(bucket.new), className: "bg-primary" },
        { value: Number(bucket.renew), className: "bg-success" },
        { value: Number(bucket.change), className: "bg-warning" },
      ],
      marker: isAll ? undefined : Number(bucket.previous_total),
    };
  });

  const groupRows = (groups: RevenueGroup[], label: (key: string) => string): BarRow[] =>
    groups.map((group) => ({
      key: group.key,
      label: label(group.key),
      value: Number(group.revenue),
      cells: [count(group.payments), money(group.revenue), sharePct(Number(group.revenue))],
    }));
  const groupHead = (first: string) => [first, "", t("analytics.revenue.sales"), t("analytics.revenue.revenue"), t("analytics.revenue.share")];
  const empty = t("analytics.emptyPeriod");

  const legend = [
    { className: "bg-primary", label: t("analytics.revenue.new") },
    { className: "bg-success", label: t("analytics.revenue.renew") },
    { className: "bg-warning", label: t("analytics.revenue.change") },
    ...(isAll ? [] : [{ className: "border-muted-foreground/60", label: t("analytics.revenue.previous"), line: true }]),
  ];

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          highlighted
          icon={CreditCard}
          label={t("analytics.revenue.revenue")}
          value={money(totals.revenue)}
          trend={revenueTrend}
        />
        <KpiTile icon={ShoppingCart} label={t("analytics.revenue.payments")} value={count(totals.payments)} trend={paymentsTrend} />
        <KpiTile
          icon={Receipt}
          label={t("analytics.revenue.avgCheck")}
          value={money(totals.avg_check, true)}
          hint={t("analytics.revenue.medianCaption", { median: money(totals.median_check, true) })}
        />
        <KpiTile
          icon={RotateCcw}
          label={t("analytics.revenue.refunds")}
          value={count(totals.refunds)}
          hint={t("analytics.revenue.refundsCaption", {
            amount: money(totals.refunded),
            share: sharePct(Number(totals.refunded)),
          })}
        />
      </div>

      <Card>
        <CardHeader
          icon={BarChart3}
          title={t(`analytics.revenue.chartTitle.${granularity}`)}
          description={t("analytics.revenue.chartDescription")}
          aside={
            <SegmentedPills
              value={granularity}
              onChange={onGranularity}
              options={GRANULARITIES.map((value) => ({ value, label: t(`analytics.revenue.granularity.${value}`) }))}
            />
          }
        />
        <div className="flex flex-col gap-4 pt-4">
          <ColumnChart columns={columns} empty={t("analytics.revenue.chartEmpty")} />
          <Legend items={legend} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            icon={BarChart3}
            title={t("analytics.revenue.byPlan")}
            description={t("analytics.revenue.byPlanDescription")}
          />
          <BarRows head={groupHead(t("analytics.revenue.plan"))} rows={groupRows(data.by_plan, (key) => key)} empty={empty} />
        </Card>
        <Card>
          <CardHeader
            icon={BarChart3}
            title={t("analytics.revenue.byDuration")}
            description={t("analytics.revenue.byDurationDescription")}
          />
          <BarRows
            head={groupHead(t("analytics.revenue.duration"))}
            rows={groupRows(data.by_duration, (key) => t("plans.daysShort", { count: Number(key) }))}
            empty={empty}
          />
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader
            icon={BarChart3}
            title={t("analytics.revenue.byChannel")}
            description={t("analytics.revenue.byChannelDescription")}
          />
          <BarRows
            head={groupHead(t("analytics.revenue.channel"))}
            rows={groupRows(data.by_channel, (key) => t(`transactions.channel.${key}` as ParseKeys))}
            empty={empty}
          />
        </Card>
      </div>

      <Card>
        <CardHeader
          icon={CreditCard}
          title={t("analytics.revenue.gateways")}
          description={t("analytics.revenue.gatewaysDescription")}
        />
        {data.gateways.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-muted-foreground">{empty}</p>
        ) : (
          <div className="flex flex-col gap-4 pt-4">
            {data.gateways.map((gateway) => (
              <GatewayRow key={gateway.gateway_type} gateway={gateway} revenue={money(gateway.revenue)} />
            ))}
          </div>
        )}
      </Card>

      <CurrencyNote currency={currency} />
    </>
  );
}

function GatewayRow({ gateway, revenue }: { gateway: GatewayStats; revenue: string }) {
  const { t, i18n } = useTranslation();
  const attempts = gateway.paid + gateway.canceled + gateway.failed;
  const width = (value: number) => `${attempts > 0 ? (value / attempts) * 100 : 0}%`;

  return (
    <div className="flex flex-col gap-2 text-[13px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 flex-1 truncate font-semibold text-foreground">
          {t(`settings.gateways.types.${gateway.gateway_type}` as ParseKeys)}
        </span>
        {attempts > 0 && (
          <Tag>{t("analytics.revenue.successRate", { rate: formatPercent(gateway.paid / attempts, i18n.language) })}</Tag>
        )}
        <span className="tabular-nums text-foreground">{revenue}</span>
      </div>
      <div className="flex h-2 gap-[3px] overflow-hidden rounded-full bg-white/[0.06]">
        <div className="bg-success" style={{ width: width(gateway.paid) }} />
        <div className="bg-muted-foreground" style={{ width: width(gateway.canceled) }} />
        <div className="bg-error" style={{ width: width(gateway.failed) }} />
      </div>
      <span className="text-[12px] text-muted-foreground">
        {t("analytics.revenue.gatewayCaption", {
          paid: gateway.paid.toLocaleString(i18n.language),
          canceled: gateway.canceled.toLocaleString(i18n.language),
          failed: gateway.failed.toLocaleString(i18n.language),
          refunded: gateway.refunded.toLocaleString(i18n.language),
        })}
      </span>
    </div>
  );
}
