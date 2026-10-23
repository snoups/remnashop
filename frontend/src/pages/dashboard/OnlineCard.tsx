import { Wifi } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getOnlineChart } from "@entities/overview/api";
import type { HourlyOnline } from "@entities/overview/api";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { fillDailySeries, formatChartDay, useChart } from "@pages/dashboard/chart-data";
import { TrendChart } from "@pages/dashboard/charts";

type View = "hours" | 7 | 30;

const COLOR = "var(--color-primary)";

function OnlineView({
  current,
  peakTag,
  data,
  xFormatter,
  isEmpty = false,
}: {
  current: number;
  peakTag: string | null;
  data: { x: string; value: number | null }[];
  xFormatter: (x: string) => string;
  isEmpty?: boolean;
}) {
  const { t, i18n } = useTranslation();
  return (
    <div className="flex flex-col gap-3 pt-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="text-2xl font-bold text-foreground">{current.toLocaleString(i18n.language)}</span>
        {peakTag && <Tag>{peakTag}</Tag>}
      </div>
      <TrendChart
        data={data}
        color={COLOR}
        valueName={t("dashboard.online.valueName")}
        valueFormatter={(value) => value.toLocaleString(i18n.language)}
        xFormatter={xFormatter}
      />
      {isEmpty && <p className="text-center text-[13px] text-muted-foreground">{t("dashboard.online.empty")}</p>}
    </div>
  );
}

function HourlyBody({ state }: { state: AsyncState<HourlyOnline> }) {
  const { t, i18n } = useTranslation();
  if (state.kind === "loading") return <Spinner size="card" />;
  if (state.kind === "error") return <ErrorState text={t("common.loadError")} />;

  const hourLabel = (iso: string) =>
    new Date(iso)
      .toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
      .replace(/:\d\d$/, ":00");
  const measured = state.data.points.filter((point) => point.peak !== null);
  const top = measured.reduce<(typeof measured)[number] | null>(
    (best, point) => (best === null || (point.peak ?? 0) > (best.peak ?? 0) ? point : best),
    null,
  );

  return (
    <OnlineView
      current={state.data.current}
      peakTag={
        top
          ? t("dashboard.online.peak", { peak: (top.peak ?? 0).toLocaleString(i18n.language), time: hourLabel(top.hour) })
          : null
      }
      data={state.data.points.map((point) => ({ x: point.hour, value: point.peak }))}
      xFormatter={hourLabel}
      isEmpty={measured.length === 0}
    />
  );
}

function DailyBody({ days, refreshKey }: { days: 7 | 30; refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const state = useChart(getOnlineChart, days, refreshKey);
  if (state.kind === "loading") return <Spinner size="card" />;
  if (state.kind === "error") return <ErrorState text={t("common.loadError")} />;

  const series = fillDailySeries(state.data.daily_peak, state.data.days, (day) => ({ day, count: 0 }));
  return (
    <OnlineView
      current={state.data.current}
      peakTag={null}
      data={series.map((point) => ({ x: point.day, value: point.count }))}
      xFormatter={(x) => formatChartDay(x, i18n.language)}
    />
  );
}

export function OnlineCard({
  hourlyState,
  refreshKey,
}: {
  hourlyState: AsyncState<HourlyOnline>;
  refreshKey: number;
}) {
  const { t } = useTranslation();
  const [view, setView] = useState<View>("hours");
  const options = [
    { value: "hours" as const, label: t("dashboard.online.hours24") },
    { value: 7 as const, label: t("dashboard.periodDays", { count: 7 }) },
    { value: 30 as const, label: t("dashboard.periodDays", { count: 30 }) },
  ];

  return (
    <Card>
      <CardHeader
        icon={Wifi}
        title={t("dashboard.online.title")}
        description={t("dashboard.online.description")}
        aside={<SegmentedPills value={view} onChange={setView} options={options} />}
      />
      {view === "hours" ? <HourlyBody state={hourlyState} /> : <DailyBody days={view} refreshKey={refreshKey} />}
    </Card>
  );
}
