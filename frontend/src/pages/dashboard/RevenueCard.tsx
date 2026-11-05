import { Wallet } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getRevenueChart } from "@entities/overview/api";
import { formatMoney } from "@shared/lib/format";
import { FieldHint } from "@shared/ui/FieldHint";
import { KPI_VALUE_CLASS } from "@shared/ui/classes";
import { Section } from "@shared/ui/glass/Section";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { fillDailySeries, formatChartDay, formatChartDayLong, useChart } from "@pages/dashboard/chart-data";
import { TrendChart } from "@pages/dashboard/charts";

const PERIODS = [7, 30, 90] as const;

export function RevenueCard({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [days, setDays] = useState<(typeof PERIODS)[number]>(7);
  const state = useChart(getRevenueChart, days, refreshKey);

  const report = state.kind === "ready" ? state.data : null;
  const series = report ? fillDailySeries(report.daily, report.days, (day) => ({ day, amount: "0", count: 0 })) : [];
  const total = series.reduce((sum, point) => sum + Number(point.amount), 0);

  return (
    <Section
      icon={Wallet}
      title={
        <>
          {t("dashboard.revenue.title")}
          {report && <FieldHint glass text={t("analytics.currencyNote", { currency: report.report_currency })} />}
        </>
      }
      description={t("dashboard.revenue.description")}
      aside={
        <SegmentedPills
          value={days}
          onChange={setDays}
          options={PERIODS.map((value) => ({ value, label: t("dashboard.periodDays", { count: value }) }))}
        />
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {report && (
        <div className="flex flex-col gap-3 pt-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className={`${KPI_VALUE_CLASS} text-foreground`}>
              {formatMoney(total, report.report_currency, i18n.language)}
            </span>
            <Tag>
              {t("dashboard.revenue.orders", {
                count: report.paid_orders_count,
                formatted: report.paid_orders_count.toLocaleString(i18n.language),
              })}
            </Tag>
          </div>
          <TrendChart
            data={series.map((point) => ({
              x: point.day,
              value: Number(point.amount),
              detail: point.count.toLocaleString(i18n.language),
            }))}
            color="var(--color-success)"
            valueName={t("dashboard.revenue.valueName")}
            detailName={t("dashboard.revenue.transactions")}
            valueFormatter={(value) => formatMoney(value, report.report_currency, i18n.language, true)}
            xFormatter={(x) => formatChartDay(x, i18n.language)}
            labelFormatter={(x) => formatChartDayLong(x, i18n.language)}
          />
        </div>
      )}
    </Section>
  );
}
