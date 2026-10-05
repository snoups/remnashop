import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { LIST_HEAD_CLASS } from "@shared/ui/classes";

const FILL_CLASS = { primary: "bg-primary", warning: "bg-warning", success: "bg-success" } as const;
const MAX_LABELED_COLUMNS = 14;

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  cells: ReactNode[];
  tone?: keyof typeof FILL_CLASS;
}

function Empty({ text }: { text: string }) {
  return <p className="py-6 text-center text-[13px] text-muted-foreground">{text}</p>;
}

export function BarRows({ head, rows, empty }: { head?: string[]; rows: BarRow[]; empty: string }) {
  if (rows.length === 0) return <Empty text={empty} />;

  const max = Math.max(...rows.map((row) => row.value));
  const cellCount = Math.max(head ? head.length - 2 : 0, ...rows.map((row) => row.cells.length));
  const gridTemplateColumns = `minmax(0,1.4fr) minmax(0,2fr)${cellCount > 0 ? ` repeat(${cellCount}, auto)` : ""}`;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[480px]">
        {head && (
          <div className={`grid gap-4 ${LIST_HEAD_CLASS}`} style={{ gridTemplateColumns }}>
            {head.map((label, index) => (
              <span key={index} className={index > 1 ? "text-right" : ""}>
                {label}
              </span>
            ))}
          </div>
        )}
        {rows.map((row) => (
          <div key={row.key} className="grid items-center gap-4 px-3 py-2 text-[13px]" style={{ gridTemplateColumns }}>
            <span className="truncate text-foreground">{row.label}</span>
            <div className="h-2 rounded-full bg-white/[0.06]">
              <div
                className={`h-full rounded-full ${FILL_CLASS[row.tone ?? "primary"]}`}
                style={{ width: `${max > 0 ? (row.value / max) * 100 : 0}%` }}
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
  if (columns.length === 0) return <Empty text={empty} />;

  const total = (column: Column) => column.segments.reduce((sum, segment) => sum + segment.value, 0);
  const max = Math.max(...columns.map((column) => Math.max(total(column), column.marker ?? 0)));
  const scale = (value: number) => (max > 0 ? (value / max) * height : 0);
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
            <div className="relative flex w-full flex-col-reverse" style={{ height: scale(total(column)) }}>
              {column.marker !== undefined && (
                <div
                  className="absolute inset-x-0 border-t border-dashed border-muted-foreground/60"
                  style={{ bottom: scale(column.marker) }}
                />
              )}
              {column.segments.map((segment, segmentIndex) => (
                <div
                  key={segmentIndex}
                  className={`w-full last:rounded-t-md ${segment.className}`}
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
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-muted-foreground">
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
  return <p className="text-[12px] text-muted-foreground">{t("analytics.currencyNote", { currency })}</p>;
}
