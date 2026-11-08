import { CalendarRange } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { formatMoney } from "@shared/lib/format";
import type { TransactionItem, PurchaseType } from "@entities/transactions/api";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { PURCHASE_TYPE_BAR_CLASS } from "@features/user-details/purchase-type";
import { DAY_MS } from "@shared/lib/period";

// narrower segments/gaps drop their text label, it would overlap the neighbour
const MIN_LABEL_PCT = 10;
const MAX_MONTH_TICKS = 8;

const LEGEND_TYPES: readonly PurchaseType[] = ["NEW", "RENEW", "CHANGE"];

// one lane per row of bars: a bar's label sits above it, the next lane starts right under it
const LANE_PX = 44;
const BAR_TOP_PX = 18;
const BAR_PX = 22;

interface Segment {
  order: TransactionItem;
  start: number;
  end: number;
  lane: number;
}

// A renewal extends its own subscription's period, starting where that one ends if it's
// still ahead; a plan change carries the chain on to the subscription it creates and cuts the
// replaced period short. A renewal or change with no subscription link (a migrated order, or
// one not reconciled yet) continues the latest chain; an unlinked purchase starts its own.
function buildSegments(paid: TransactionItem[]): Segment[] {
  const chainOf = new Map<number, string>();
  const chainEnd = new Map<string, number>();
  const placed: { order: TransactionItem; start: number; end: number; chain: string }[] = [];
  let lastChain: string | undefined;
  for (const order of paid) {
    const linked = order.target_subscription_id ?? order.fulfilled_subscription_id;
    const continued = order.purchase_type !== "NEW";
    const chain =
      (continued && order.target_subscription_id !== null ? chainOf.get(order.target_subscription_id) : undefined) ??
      (linked !== null ? `sub-${linked}` : continued && lastChain !== undefined ? lastChain : `order-${order.id}`);
    lastChain = chain;
    for (const id of [order.target_subscription_id, order.fulfilled_subscription_id]) {
      if (id !== null) chainOf.set(id, chain);
    }
    const created = new Date(order.created_at).getTime();
    const start = order.purchase_type === "RENEW" ? Math.max(created, chainEnd.get(chain) ?? 0) : created;
    const end = start + order.duration_days * DAY_MS;
    if (order.purchase_type === "CHANGE") {
      for (const earlier of placed) if (earlier.chain === chain) earlier.end = Math.min(earlier.end, start);
    }
    chainEnd.set(chain, order.purchase_type === "CHANGE" ? end : Math.max(chainEnd.get(chain) ?? 0, end));
    placed.push({ order, start, end, chain });
  }

  // chains that don't overlap in time share a lane
  const extent = new Map<string, [number, number]>();
  for (const { chain, start, end } of placed) {
    const [from, to] = extent.get(chain) ?? [start, end];
    extent.set(chain, [Math.min(from, start), Math.max(to, end)]);
  }
  const laneEnds: number[] = [];
  const laneOf = new Map<string, number>();
  for (const [chain, [from, to]] of [...extent].sort((a, b) => a[1][0] - b[1][0])) {
    const free = laneEnds.findIndex((laneEnd) => laneEnd <= from);
    const lane = free === -1 ? laneEnds.length : free;
    laneEnds[lane] = to;
    laneOf.set(chain, lane);
  }
  return placed.map(({ order, start, end, chain }) => ({ order, start, end, lane: laneOf.get(chain)! }));
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
export function PaidTimeline({ orders }: { orders: TransactionItem[] }) {
  const { t, i18n } = useTranslation();
  const byDate = [...orders].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const segments = buildSegments(byDate.filter((order) => order.status === "PAID"));
  const refunds = byDate.filter((order) => order.status === "REFUNDED");
  const laneOfSubscription = new Map<number, number>();
  for (const { order, lane } of segments) {
    for (const id of [order.target_subscription_id, order.fulfilled_subscription_id]) {
      if (id !== null) laneOfSubscription.set(id, lane);
    }
  }
  if (segments.length === 0) {
    return (
      <DialogCard variant="form" title={t("users.details.analytics.timeline.title")} icon={CalendarRange}>
        <EmptyState text={t("users.details.analytics.timeline.empty")} />
      </DialogCard>
    );
  }

  const now = Date.now();
  const lanes = Math.max(...segments.map(({ lane }) => lane)) + 1;
  const barsBottom = (lanes - 1) * LANE_PX + BAR_TOP_PX + BAR_PX;
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
      <span className="max-w-56 pt-0.5 text-muted-foreground">{t("users.details.analytics.timeline.freeNote")}</span>
    </span>
  );
  const title = (
    <>
      {t("users.details.analytics.timeline.title")}
      {/* the Card title is uppercase; the bubble inherits it otherwise */}
      <span className="inline-flex font-medium normal-case tracking-normal">
        <FieldHint
          text={`${legendItems.map(([, label]) => label).join(", ")}. ${t("users.details.analytics.timeline.freeNote")}`}
          content={legend}
          side="bottom"
        />
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
    <DialogCard variant="form" title={title} icon={CalendarRange}>
      <p className="-mt-1 text-[12px] text-muted-foreground">
        {t("users.details.analytics.timeline.coverage", {
          paid: Math.round(paidDays),
          total: Math.max(1, Math.round(totalDays)),
        })}
        {gaps.length > 0 && ` · ${t("users.details.analytics.timeline.gaps", { count: gaps.length })}`}
      </p>
      <div>
        <div className="relative" style={{ height: barsBottom + 24 }}>
          {segments.map(({ order, start, end, lane }) => (
            <div key={order.id}>
              <div
                className={`absolute rounded-full ${PURCHASE_TYPE_BAR_CLASS[order.purchase_type]}`}
                style={{
                  top: lane * LANE_PX + BAR_TOP_PX,
                  height: BAR_PX,
                  left: `${pct(start)}%`,
                  width: `calc(${pct(end) - pct(start)}% - 2px)`,
                }}
              />
              {pct(end) - pct(start) >= MIN_LABEL_PCT && (
                <span
                  className="absolute whitespace-nowrap text-[11px] font-semibold tabular-nums text-foreground"
                  style={{ top: lane * LANE_PX, left: `${pct(start)}%` }}
                >
                  {formatMoney(order.final_price, order.currency, i18n.language, true)}
                </span>
              )}
            </div>
          ))}
          {gaps.map(([start, end]) => (
            <div key={start}>
              {/* no subscription at all: centred across every lane */}
              <div
                className="absolute border-t-2 border-dashed border-error/70"
                style={{
                  top: (BAR_TOP_PX + barsBottom) / 2 - 1,
                  left: `${pct(start)}%`,
                  width: `${pct(end) - pct(start)}%`,
                }}
              />
              {pct(end) - pct(start) >= MIN_LABEL_PCT && (
                <span
                  className="absolute whitespace-nowrap pl-1 text-[11px] text-error"
                  style={{ top: barsBottom + 6, left: `${pct(start)}%` }}
                >
                  {t("users.details.analytics.timeline.gap", { count: Math.round((end - start) / DAY_MS) })}
                </span>
              )}
            </div>
          ))}
          {refunds.map((order) => {
            const subscription = order.target_subscription_id ?? order.fulfilled_subscription_id;
            const lane = (subscription !== null && laneOfSubscription.get(subscription)) || 0;
            return (
              <div
                key={order.id}
                className="absolute size-2.5 -translate-x-1/2 rounded-full border-2 border-warning bg-canvas"
                style={{ top: lane * LANE_PX + 13, left: `${pct(new Date(order.created_at).getTime())}%` }}
              />
            );
          })}
          <div
            className="absolute top-3 w-px bg-foreground/60"
            style={{ height: barsBottom - 12 + 8, left: `${pct(now)}%` }}
          />
        </div>
        <div className="relative h-5 border-t border-white/[0.08]">
          {months.map((month, index) =>
            index % tickStep === 0 ? (
              <span
                key={month}
                className="absolute top-1 text-[11px] text-muted-foreground"
                style={{ left: `${pct(month)}%` }}
              >
                {monthLabel(month)}
              </span>
            ) : null,
          )}
        </div>
      </div>
    </DialogCard>
  );
}
