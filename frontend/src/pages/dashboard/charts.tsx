import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART_TICK, CHART_TOOLTIP_STYLE } from "@pages/dashboard/chart-data";

export function TrendChart({
  data,
  color,
  valueName,
  valueFormatter,
  xFormatter,
}: {
  data: { x: string; value: number | null }[];
  color: string;
  valueName: string;
  valueFormatter: (value: number) => string;
  xFormatter: (x: string) => string;
}) {
  const gradientId = useId();
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
          labelFormatter={(label) => xFormatter(String(label))}
          formatter={(value) => valueFormatter(Number(value))}
          {...CHART_TOOLTIP_STYLE}
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
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
