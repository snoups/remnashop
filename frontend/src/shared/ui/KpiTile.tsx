import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { animate } from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";

import { FieldHint } from "@shared/ui/FieldHint";

export interface KpiTrend {
  /** signed change over the period, shown as +N / −N / 0 */
  delta: number;
  /** formatted magnitude (e.g. a percent) in place of |delta|; the sign still comes from delta */
  text?: string;
  /** the period, after the change */
  hint: string;
}

function trendTone(delta: number): { Icon: ComponentType<{ className?: string }>; badge: string; text: string } {
  if (delta > 0) return { Icon: TrendingUp, badge: "bg-success/10 text-success", text: "text-success" };
  if (delta < 0) return { Icon: TrendingDown, badge: "bg-error/10 text-error", text: "text-error" };
  return { Icon: Minus, badge: "bg-white/[0.06] text-muted-foreground", text: "text-muted-foreground" };
}

// First number in an already-formatted value ("1 234 ₽", "12,5%", "$1,234.56"):
// 1–2 digits after the last . or , are a fraction, anything else is grouping.
const NUMBER_RUN = /\d(?:[\d\s.,]*\d)?/;

interface ParsedNumber {
  prefix: string;
  suffix: string;
  value: number;
  fraction: number;
  decimalSep: string;
  groupSep: string;
}

function parseNumber(text: string): ParsedNumber | null {
  const match = NUMBER_RUN.exec(text);
  if (!match) return null;
  const run = match[0];
  const decimal = /[.,](\d{1,2})$/.exec(run);
  const fraction = decimal ? decimal[1].length : 0;
  const intPart = decimal ? run.slice(0, -(fraction + 1)) : run;
  return {
    prefix: text.slice(0, match.index),
    suffix: text.slice(match.index + run.length),
    value: Number(intPart.replace(/\D/g, "") + (decimal ? `.${decimal[1]}` : "")),
    fraction,
    decimalSep: decimal ? run[run.length - fraction - 1] : "",
    groupSep: /\D/.exec(intPart)?.[0] ?? "",
  };
}

function formatParsed(parsed: ParsedNumber, value: number): string {
  const [int, frac] = value.toFixed(parsed.fraction).split(".");
  const grouped = parsed.groupSep ? int.replace(/\B(?=(\d{3})+(?!\d))/g, parsed.groupSep) : int;
  return `${parsed.prefix}${grouped}${frac ? parsed.decimalSep + frac : ""}${parsed.suffix}`;
}

// Counts up to the value on load and from the old value on change, keeping the caller's formatting.
function CountUp({ text }: { text: string }) {
  const parsed = parseNumber(text);
  const target = parsed?.value;
  const fromRef = useRef(0);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (target === undefined) return;
    const controls = animate(fromRef.current, target, {
      duration: 0.8,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (latest) => {
        fromRef.current = latest;
        setShown(latest);
      },
    });
    return () => controls.stop();
  }, [target]);

  return <>{parsed ? formatParsed(parsed, shown) : text}</>;
}

export function KpiTile({
  label,
  value,
  hint,
  trend,
  info,
  icon: Icon,
  highlighted = false,
  valueClassName = "text-foreground",
  valueSuffix,
}: {
  label: string;
  value: string;
  /** line under the value */
  hint?: ReactNode;
  /** icon next to the value, the change and its period on a line under it */
  trend?: KpiTrend;
  /** FieldHint next to the label */
  info?: string;
  icon?: ComponentType<{ className?: string }>;
  highlighted?: boolean;
  /** overrides the value's color, e.g. ROI green/red */
  valueClassName?: string;
  /** muted text right after the value, e.g. "of 5" */
  valueSuffix?: string;
}) {
  const tone = trend && trendTone(trend.delta);
  return (
    <div
      className={`flex min-w-0 flex-col gap-1.5 rounded-2xl border px-[18px] py-4 ${
        highlighted ? "border-primary/25 bg-accent/60" : "border-white/[0.08] bg-white/[0.03]"
      }`}
    >
      <div className="flex items-center gap-2.5">
        {Icon && (
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Icon className="size-5" />
          </div>
        )}
        <span
          className={`whitespace-pre-line text-[11px] font-semibold uppercase tracking-wide ${
            highlighted ? "text-accent-foreground" : "text-muted-foreground"
          }`}
        >
          {label}
        </span>
        {info && <FieldHint text={info} />}
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-[26px] font-bold tabular-nums tracking-tight ${valueClassName}`}>
          <CountUp text={value} />
        </span>
        {valueSuffix && <span className="text-[13px] font-medium text-muted-foreground">{valueSuffix}</span>}
        {tone && (
          <span className={`flex size-6 shrink-0 items-center justify-center rounded-full ${tone.badge}`}>
            <tone.Icon className="size-3.5" />
          </span>
        )}
      </div>
      {trend && tone && (
        <span className="text-[12px] text-muted-foreground">
          <span className={`font-semibold tabular-nums ${tone.text}`}>
            {trend.delta > 0 ? "+" : trend.delta < 0 ? "−" : ""}
            {trend.text ?? Math.abs(trend.delta)}
          </span>
          {` · ${trend.hint}`}
        </span>
      )}
      {/* mt-auto: hints line up across a grid row where only some tiles have a trend line */}
      {hint && <span className="mt-auto text-[12px] tabular-nums text-muted-foreground">{hint}</span>}
    </div>
  );
}
