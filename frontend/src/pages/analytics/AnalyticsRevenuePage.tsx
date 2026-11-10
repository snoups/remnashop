import { BarChart3, CreditCard, Package, Receipt, RotateCcw } from "lucide-react";
import type { ParseKeys } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getRevenue } from "@entities/analytics/api";
import type { AnalyticsPeriod, GatewayStats, Revenue, RevenueGranularity, RevenueGroup } from "@entities/analytics/api";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { DAY_MS } from "@shared/lib/period";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Section } from "@shared/ui/glass/Section";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { BarRows, ColumnChart, Legend } from "@pages/analytics/charts";
import type { BarRow } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, previousPeriodHint, relativeTrend } from "@pages/analytics/trends";

const GRANULARITIES: RevenueGranularity[] = ["day", "week", "month"];
const MAX_DAILY_RANGE_DAYS = 92;
const GROUPS = ["plan", "duration", "channel"] as const;
const GROUP_KEYS = { plan: "byPlan", duration: "byDuration", channel: "byChannel" } as const;

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
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
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
  const vs = previousPeriodHint(useAnalyticsPeriod().period, t);
  const [group, setGroup] = useState<(typeof GROUPS)[number]>("plan");
  const language = i18n.language;
  const currency = data.report_currency;
  const { totals } = data;
  const money = (value: string | number, exact = false) => formatMoney(value, currency, language, exact);
  const revenue = Number(totals.revenue);
  const sharePct = (value: number) => formatPercent(revenue > 0 ? value / revenue : 0, language);

  const count = (value: number) => value.toLocaleString(language);
  const revenueTrend = isAll
    ? undefined
    : relativeTrend(revenue, Number(totals.previous_revenue), vs, language);
  const paymentsTrend = isAll ? undefined : countTrend(totals.payments, totals.previous_payments, vs, language);
  const avgCheckTrend =
    isAll || totals.payments === 0 || totals.previous_payments === 0
      ? undefined
      : relativeTrend(Number(totals.avg_check), Number(totals.previous_revenue) / totals.previous_payments, vs, language);
  const refundsTrend = isAll
    ? undefined
    : { ...countTrend(totals.refunds, totals.previous_refunds, vs, language), lowerIsBetter: true };

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
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          panel
          icon={CreditCard}
          label={t("analytics.revenue.revenue")}
          value={money(totals.revenue)}
          trend={revenueTrend}
        />
        <KpiTile panel icon={Receipt} label={t("analytics.revenue.payments")} value={count(totals.payments)} trend={paymentsTrend} />
        <KpiTile
          panel
          icon={Receipt}
          label={t("analytics.revenue.avgCheck")}
          value={totals.payments > 0 ? money(totals.avg_check, true) : t("common.none")}
          trend={avgCheckTrend}
          hint={totals.payments > 0 ? t("analytics.revenue.medianCaption", { median: money(totals.median_check, true) }) : undefined}
        />
        <KpiTile
          panel
          icon={RotateCcw}
          label={t("analytics.revenue.refunds")}
          value={count(totals.refunds)}
          trend={refundsTrend}
          hint={t("analytics.revenue.refundsCaption", {
            amount: money(totals.refunded),
            share: sharePct(Number(totals.refunded)),
          })}
        />
      </div>

      <Section
        icon={BarChart3}
        title={t(`analytics.revenue.chartTitle.${granularity}`)}
        description={t("analytics.revenue.chartDescription")}
        aside={
          <PillTabs
            activeKey={granularity}
            onSelect={onGranularity}
            items={GRANULARITIES.map((key) => ({ key, label: t(`analytics.revenue.granularity.${key}`) }))}
          />
        }
      >
        <div className="flex flex-col gap-4 px-3.5 pt-4">
          <ColumnChart columns={columns} empty={t("analytics.revenue.chartEmpty")} />
          <Legend items={legend} />
        </div>
      </Section>

      <Section
        icon={Package}
        title={t("analytics.revenue.breakdown")}
        description={t(`analytics.revenue.${GROUP_KEYS[group]}Description`)}
        aside={
          <PillTabs
            activeKey={group}
            onSelect={setGroup}
            items={GROUPS.map((key) => ({ key, label: t(`analytics.revenue.${GROUP_KEYS[key]}`) }))}
          />
        }
      >
        {group === "plan" && (
          <BarRows head={groupHead(t("analytics.revenue.plan"))} rows={groupRows(data.by_plan, (key) => key)} empty={empty} />
        )}
        {group === "duration" && (
          <BarRows
            head={groupHead(t("analytics.revenue.duration"))}
            rows={groupRows(data.by_duration, (key) => t("plans.daysShort", { count: Number(key) }))}
            empty={empty}
          />
        )}
        {group === "channel" && (
          <BarRows
            head={groupHead(t("analytics.revenue.channel"))}
            rows={groupRows(data.by_channel, (key) => t(`transactions.channel.${key}` as ParseKeys))}
            empty={empty}
          />
        )}
      </Section>

      <Section
        icon={CreditCard}
        title={t("analytics.revenue.gateways")}
        description={t("analytics.revenue.gatewaysDescription")}
      >
        {data.gateways.length === 0 ? (
          <EmptyState text={empty} />
        ) : (
          <div className="flex flex-col gap-4 px-3.5 pt-4">
            {data.gateways.map((gateway) => (
              <GatewayRow key={gateway.gateway_type} gateway={gateway} revenue={money(gateway.revenue)} />
            ))}
          </div>
        )}
      </Section>

    </>
  );
}

function GatewayRow({ gateway, revenue }: { gateway: GatewayStats; revenue: string }) {
  const { t, i18n } = useTranslation();
  const attempts = gateway.paid + gateway.canceled + gateway.failed;
  const width = (value: number) => `${attempts > 0 ? (value / attempts) * 100 : 0}%`;

  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 flex-1 truncate font-semibold text-foreground">
          {t(`settings.gateways.types.${gateway.gateway_type}` as ParseKeys)}
        </span>
        {attempts > 0 && (
          <Tag>{t("analytics.revenue.successRate", { rate: formatPercent(gateway.paid / attempts, i18n.language) })}</Tag>
        )}
        <span className="tabular-nums text-foreground">{revenue}</span>
      </div>
      <div className="flex h-2 gap-[3px] overflow-hidden rounded-full glass-track">
        <div className="bg-success transition-[width] duration-200 ease-out" style={{ width: width(gateway.paid) }} />
        <div className="bg-muted-foreground transition-[width] duration-200 ease-out" style={{ width: width(gateway.canceled) }} />
        <div className="bg-error transition-[width] duration-200 ease-out" style={{ width: width(gateway.failed) }} />
      </div>
      <span className="text-xs text-muted-foreground">
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
