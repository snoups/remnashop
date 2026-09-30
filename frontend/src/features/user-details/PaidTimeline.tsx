import { CalendarRange } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { formatMoney } from "@entities/advertising/format";
import type { PaymentOrderItem, PurchaseType } from "@entities/payments/api";
import { Card } from "@shared/ui/Card";
import { EmptyState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { PURCHASE_TYPE_BAR_CLASS } from "@features/user-details/purchase-type";

const DAY_MS = 86_400_000;
// narrower segments/gaps drop their text label, it would overlap the neighbour
const MIN_LABEL_PCT = 10;
const MAX_MONTH_TICKS = 8;

const LEGEND_TYPES: readonly PurchaseType[] = ["NEW", "RENEW", "CHANGE"];

interface Segment {
  order: PaymentOrderItem;
  start: number;
  end: number;
}

// A renewal extends the period it renews, so it starts where the previous paid period ends
// if that is still ahead. chains onto the latest period of any subscription, a user
// renewing one of two parallel subscriptions gets a slightly shifted bar.
function buildSegments(paid: PaymentOrderItem[]): Segment[] {
  let lastEnd = 0;
  return paid.map((order) => {
    const created = new Date(order.created_at).getTime();
    const start = order.purchase_type === "RENEW" ? Math.max(created, lastEnd) : created;
    const end = start + order.duration_days * DAY_MS;
    lastEnd = Math.max(lastEnd, end);
    return { order, start, end };
  });
}

function mergeIntervals(segments: Segment[]): [number, number][] {
  const merged: [number, number][] = [];
  for (const { start, end } of [...segments].sort((a, b) => a.start - b.start)) {
    const last = merged.at(-1);
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

function monthStart(time: number, offset = 0): number {
  const date = new Date(time);
  return new Date(date.getFullYear(), date.getMonth() + offset, 1).getTime();
}

/** Paid periods on a time axis: one bar per paid order over the days it bought, gaps between them, refunds as dots. */
export function PaidTimeline({ orders }: { orders: PaymentOrderItem[] }) {
  const { t, i18n } = useTranslation();
  const byDate = [...orders].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const segments = buildSegments(byDate.filter((order) => order.status === "PAID"));
  const refunds = byDate.filter((order) => order.status === "REFUNDED");
  if (segments.length === 0) {
    return (
      <Card variant="form" title={t("users.details.analytics.timeline.title")} icon={CalendarRange}>
        <EmptyState text={t("users.details.analytics.timeline.empty")} />
      </Card>
    );
  }

  const now = Date.now();
  const intervals = mergeIntervals(segments);
  const gaps: [number, number][] = [];
  intervals.forEach(([, end], index) => {
    const next = intervals[index + 1]?.[0] ?? now;
    if (end < Math.min(next, now)) gaps.push([end, Math.min(next, now)]);
  });
  const firstStart = intervals[0][0];
  const paidDays = intervals.reduce((sum, [start, end]) => sum + Math.max(0, Math.min(end, now) - start), 0) / DAY_MS;
  const totalDays = (now - firstStart) / DAY_MS;

  // only what this chart actually draws
  const types = new Set(segments.map(({ order }) => order.purchase_type));
  const legendItems: [ReactNode, string][] = [
    ...LEGEND_TYPES.filter((type) => types.has(type)).map((type): [ReactNode, string] => [
      <span key={type} className={`h-2 w-4 rounded-full ${PURCHASE_TYPE_BAR_CLASS[type]}`} />,
      t(`users.details.analytics.timeline.legend.${type}`),
    ]),
    ...(gaps.length > 0
      ? [[<span key="gap" className="w-4 border-t-2 border-dashed border-error/70" />, t("users.details.analytics.timeline.legend.gap")] as [ReactNode, string]]
      : []),
    ...(refunds.length > 0
      ? [[<span key="refund" className="mx-[3px] size-2.5 rounded-full border-2 border-warning" />, t("users.details.analytics.timeline.legend.refund")] as [ReactNode, string]]
      : []),
    [<span key="today" className="mx-[7.5px] h-3 w-px bg-foreground/60" />, t("users.details.analytics.timeline.legend.today")],
  ];
  const legend = (
    <span className="flex flex-col gap-1.5">
      {legendItems.map(([swatch, label]) => (
        <span key={label} className="flex items-center gap-2">
          <span className="flex w-4 shrink-0 justify-center">{swatch}</span>
          {label}
        </span>
      ))}
    </span>
  );
  const title = (
    <>
      {t("users.details.analytics.timeline.title")}
      {/* the Card title is uppercase; the bubble inherits it otherwise */}
      <span className="inline-flex font-medium normal-case tracking-normal">
        <FieldHint text={legendItems.map(([, label]) => label).join(", ")} content={legend} side="bottom" />
      </span>
    </>
  );

  const axisStart = monthStart(firstStart);
  const axisEnd = monthStart(Math.max(now, intervals.at(-1)![1]), 1);
  const pct = (time: number) => ((time - axisStart) / (axisEnd - axisStart)) * 100;
  const months: number[] = [];
  for (let month = axisStart; month < axisEnd; month = monthStart(month, 1)) months.push(month);
  const tickStep = Math.ceil(months.length / MAX_MONTH_TICKS);
  const monthFormat = new Intl.DateTimeFormat(i18n.language, { month: "short" });
  // "short" is "июнь"/"авг."/"сент." in ru: cut to three letters so every tick reads alike
  const monthLabel = (month: number) => {
    const name = monthFormat.format(month).replace(".", "").slice(0, 3);
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  return (
    <Card variant="form" title={title} icon={CalendarRange}>
      <p className="-mt-1 text-[12px] text-muted-foreground">
        {t("users.details.analytics.timeline.coverage", {
          paid: Math.round(paidDays),
          total: Math.max(1, Math.round(totalDays)),
        })}
        {gaps.length > 0 && ` · ${t("users.details.analytics.timeline.gaps", { count: gaps.length })}`}
      </p>
      <div>
        <div className="relative h-16">
          {segments.map(({ order, start, end }) => (
            <div key={order.id}>
              <div
                className={`absolute top-[18px] h-[22px] rounded-full ${PURCHASE_TYPE_BAR_CLASS[order.purchase_type]}`}
                style={{ left: `${pct(start)}%`, width: `calc(${pct(end) - pct(start)}% - 2px)` }}
              />
              {pct(end) - pct(start) >= MIN_LABEL_PCT && (
                <span
                  className="absolute top-0 whitespace-nowrap text-[10.5px] font-semibold tabular-nums text-foreground"
                  style={{ left: `${pct(start)}%` }}
                >
                  {formatMoney(order.final_price, order.currency, i18n.language)}
                </span>
              )}
            </div>
          ))}
          {gaps.map(([start, end]) => (
            <div key={start}>
              <div
                className="absolute top-[28px] border-t-2 border-dashed border-error/70"
                style={{ left: `${pct(start)}%`, width: `${pct(end) - pct(start)}%` }}
              />
              {pct(end) - pct(start) >= MIN_LABEL_PCT && (
                <span
                  className="absolute top-[46px] whitespace-nowrap pl-1 text-[10.5px] text-error"
                  style={{ left: `${pct(start)}%` }}
                >
                  {t("users.details.analytics.timeline.gap", { count: Math.round((end - start) / DAY_MS) })}
                </span>
              )}
            </div>
          ))}
          {refunds.map((order) => (
            <div
              key={order.id}
              className="absolute top-[13px] size-2.5 -translate-x-1/2 rounded-full border-2 border-warning bg-canvas"
              style={{ left: `${pct(new Date(order.created_at).getTime())}%` }}
            />
          ))}
          <div className="absolute top-3 h-9 w-px bg-foreground/60" style={{ left: `${pct(now)}%` }} />
        </div>
        <div className="relative h-5 border-t border-white/[0.07]">
          {months.map((month, index) =>
            index % tickStep === 0 ? (
              <span
                key={month}
                className="absolute top-1 text-[10.5px] text-muted-foreground"
                style={{ left: `${pct(month)}%` }}
              >
                {monthLabel(month)}
              </span>
            ) : null,
          )}
        </div>
      </div>
    </Card>
  );
}
