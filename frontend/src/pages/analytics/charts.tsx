import { Info } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useChartEntered } from "@shared/ui/chart";
import { GLASS_LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState } from "@shared/ui/glass/EmptyState";

const FILL_CLASS = { primary: "bg-primary", warning: "bg-warning", success: "bg-success" } as const;
const MAX_LABELED_COLUMNS = 14;
// bars grow from zero as the page fades in, and ease to new values
const GROW_CLASS = "duration-500 ease-out";

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  cells: ReactNode[];
  tone?: keyof typeof FILL_CLASS;
}

export function BarRows({
  head,
  rows,
  empty,
  compact = false,
}: {
  head?: string[];
  rows: BarRow[];
  empty: string;
  /** a half-width card: the bar as wide as the label, so the grid fits without a scroll */
  compact?: boolean;
}) {
  const entered = useChartEntered();
  if (rows.length === 0) return <EmptyState text={empty} />;

  const max = Math.max(...rows.map((row) => row.value));
  const cellCount = Math.max(head ? head.length - 2 : 0, ...rows.map((row) => row.cells.length));
  const gridTemplateColumns = `minmax(0,1.4fr) minmax(0,${compact ? "1.4fr" : "2fr"})${cellCount > 0 ? ` repeat(${cellCount}, auto)` : ""}`;

  return (
    // pt-4: under a Section's header line
    // @container: a cell can drop a word once the card is narrow
    <div className="@container overflow-x-auto pt-4">
      {/* one grid, rows on its tracks: a long number in one row moves the same column in all of them */}
      <div className={`grid gap-x-4 ${compact ? "min-w-[320px]" : "min-w-[480px]"}`} style={{ gridTemplateColumns }}>
        {head && (
          <div className={`col-span-full grid grid-cols-subgrid ${GLASS_LIST_HEAD_CLASS}`}>
            {head.map((label, index) => (
              <span key={index} className={index > 1 ? "text-right" : ""}>
                {label}
              </span>
            ))}
          </div>
        )}
        {rows.map((row) => (
          <div key={row.key} className="col-span-full grid grid-cols-subgrid items-center px-3.5 py-2 text-[13px]">
            <span className="truncate text-foreground">{row.label}</span>
            <div className="h-2 rounded-full glass-track">
              <div
                className={`h-full rounded-full transition-[width] ${GROW_CLASS} ${FILL_CLASS[row.tone ?? "primary"]}`}
                style={{ width: `${entered && max > 0 ? (row.value / max) * 100 : 0}%` }}
              />
            </div>
            {row.cells.map((cell, index) => (
              <span key={index} className="text-right tabular-nums text-foreground">
                {cell}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export interface ColumnSegment {
  value: number;
  className: string;
}

export interface Column {
  key: string;
  label: string;
  segments: ColumnSegment[];
  caption?: string;
  marker?: number;
}

export function ColumnChart({ columns, empty, height = 200 }: { columns: Column[]; empty: string; height?: number }) {
  const entered = useChartEntered();
  const total = (column: Column) => column.segments.reduce((sum, segment) => sum + segment.value, 0);
  // a lone bar still reads; only a line needs two points
  if (!columns.some((column) => total(column) > 0 || (column.marker ?? 0) > 0)) return <EmptyState text={empty} />;

  const max = Math.max(...columns.map((column) => Math.max(total(column), column.marker ?? 0)));
  const scale = (value: number) => (entered && max > 0 ? (value / max) * height : 0);
  const labelEvery = Math.ceil(columns.length / MAX_LABELED_COLUMNS);

  return (
    <div className="overflow-x-auto">
      <div className="flex items-end gap-1.5">
        {columns.map((column, index) => (
          <div key={column.key} className="flex min-w-6 flex-1 flex-col items-center gap-1.5">
            {column.caption !== undefined && (
              <span className="whitespace-nowrap text-[11px] font-semibold tabular-nums text-foreground">
                {column.caption}
              </span>
            )}
            <div className={`relative flex w-full flex-col-reverse transition-[height] ${GROW_CLASS}`} style={{ height: scale(total(column)) }}>
              {column.marker !== undefined && (
                <div
                  className={`absolute inset-x-0 border-t border-dashed border-muted-foreground/60 transition-[bottom] ${GROW_CLASS}`}
                  style={{ bottom: scale(column.marker) }}
                />
              )}
              {column.segments.map((segment, segmentIndex) => (
                <div
                  key={segmentIndex}
                  className={`w-full transition-[height] ${GROW_CLASS} last:rounded-t-md ${segment.className}`}
                  style={{ height: scale(segment.value) }}
                />
              ))}
            </div>
            <span className="h-4 whitespace-nowrap text-[11px] text-muted-foreground">
              {index % labelEvery === 0 ? column.label : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Legend({ items }: { items: { className: string; label: ReactNode; line?: boolean }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-muted-foreground">
      {items.map((item, index) => (
        <span key={index} className="inline-flex items-center gap-1.5">
          <span className={item.line ? `h-0 w-3 border-t-2 border-dashed ${item.className}` : `size-2 rounded-full ${item.className}`} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function CurrencyNote({ currency }: { currency: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-2.5 rounded-2xl border border-dashed border-white/[0.12] p-3.5">
      <Info className="mt-px size-4 shrink-0 text-muted-foreground" />
      <p className="text-[12px] leading-relaxed text-muted-foreground">{t("analytics.currencyNote", { currency })}</p>
    </div>
  );
}
