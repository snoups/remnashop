import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART_TICK } from "@pages/dashboard/chart-data";
import { CHART_CURSOR, ChartTooltip, MIN_CHART_POINTS, useChartAnimation, useChartEntered } from "@shared/ui/chart";
import { EmptyState } from "@shared/ui/glass/EmptyState";

export function TrendChart({
  data,
  color,
  valueName,
  detailName,
  valueFormatter,
  xFormatter,
  labelFormatter = xFormatter,
}: {
  /** detail: a second row in the tooltip, named detailName (a day's transactions) */
  data: { x: string; value: number | null; detail?: string }[];
  color: string;
  valueName: string;
  detailName?: string;
  valueFormatter: (value: number) => string;
  xFormatter: (x: string) => string;
  /** the tooltip's heading, xFormatter if unset */
  labelFormatter?: (x: string) => string;
}) {
  const { t } = useTranslation();
  const gradientId = useId();
  const animation = useChartAnimation();
  const entered = useChartEntered();
  if (data.filter((point) => point.value).length < MIN_CHART_POINTS) {
    return (
      <div className="flex h-[200px]">
        <EmptyState text={t("common.notEnoughData")} />
      </div>
    );
  }
  // mounts as the page fades in, so the line draws where it can be seen
  if (!entered) return <div className="h-[200px]" />;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="x" tickFormatter={xFormatter} tick={CHART_TICK} axisLine={false} tickLine={false} />
        <YAxis tick={CHART_TICK} axisLine={false} tickLine={false} width={40} />
        <Tooltip
          cursor={CHART_CURSOR}
          content={({ active, payload, label }) => {
            const point = payload?.[0];
            if (!active || point?.value === undefined || point.value === null) return null;
            const detail: string | undefined = point.payload?.detail;
            return (
              <ChartTooltip
                title={labelFormatter(String(label))}
                color={color}
                rows={[
                  { label: valueName, value: valueFormatter(Number(point.value)) },
                  ...(detailName && detail ? [{ label: detailName, value: detail }] : []),
                ]}
              />
            );
          }}
        />
        <Area
          type="monotone"
          name={valueName}
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          dot={false}
          connectNulls={false}
          {...animation}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
