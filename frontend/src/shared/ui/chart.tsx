import { useReducedMotion } from "motion/react";

import { useLoadGateOpen } from "@shared/lib/load-gate";

/** A trend needs two points with a value; one draws no line. */
export const MIN_CHART_POINTS = 2;

/** Whether a chart should show its final shape: once the surrounding LoadGate has faded in, so its
 *  entrance plays where it can be seen; at once under reduced motion. */
export function useChartEntered(): boolean {
  const isGateOpen = useLoadGateOpen();
  const reduceMotion = useReducedMotion();
  return isGateOpen || reduceMotion === true;
}

/** A recharts series' entrance, the length of KpiTile's count-up. */
export function useChartAnimation(): { isAnimationActive: boolean; animationDuration: number; animationEasing: "ease-out" } {
  const reduceMotion = useReducedMotion();
  return { isAnimationActive: !reduceMotion, animationDuration: 800, animationEasing: "ease-out" };
}

/** A chart's tooltip as the glass hint bubble: the point's heading (after the series' dot when there is
 *  one series), then a row per value. */
export function ChartTooltip({
  title,
  color,
  rows,
}: {
  title: string;
  /** a single series' colour, as a dot before the title */
  color?: string;
  rows: { label: string; value: string }[];
}) {
  return (
    <div className="glass-dialog flex flex-col gap-1 rounded-2xl px-3.5 py-2.5 text-[12px] leading-[1.5]">
      <span className="flex items-center gap-2 text-muted-foreground">
        {color && <span className="size-2 rounded-full" style={{ background: color }} />}
        {title}
      </span>
      {rows.map((row) => (
        <span key={row.label} className="flex items-center text-foreground/90">
          {row.label}
          <span className="ml-auto pl-3 font-semibold tabular-nums text-foreground">{row.value}</span>
        </span>
      ))}
    </div>
  );
}

/** recharts' cursor line under the pointer, in the glass edge colour. */
export const CHART_CURSOR = { stroke: "var(--color-glass-border)" };
