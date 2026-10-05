import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { parseIsoDate, toIsoDate } from "@shared/lib/iso-date";
import { IconButton } from "@shared/ui/IconButton";

export interface MonthCalendarProps {
  /** YYYY-MM-DD; with rangeEnd set, the start of a range */
  value: string;
  /** YYYY-MM-DD end of a range; "" while only the start is picked; omit for single-date mode */
  rangeEnd?: string;
  onPick: (isoDate: string) => void;
}

function getMonthGrid(year: number, month: number): Date[] {
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - startOffset);
  return Array.from(
    { length: 42 },
    (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  );
}

export function MonthCalendar({ value, rangeEnd, onPick }: MonthCalendarProps) {
  const { i18n } = useTranslation();
  const [viewDate, setViewDate] = useState(parseIsoDate(value) ?? new Date());

  const today = toIsoDate(new Date());
  const isRange = rangeEnd !== undefined;
  const days = getMonthGrid(viewDate.getFullYear(), viewDate.getMonth());
  const monthLabel = viewDate.toLocaleDateString(i18n.language, { month: "long", year: "numeric" });
  const weekdayLabels = Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 1 + i).toLocaleDateString(i18n.language, { weekday: "short" }),
  );

  return (
    <>
      <div className="flex items-center justify-between">
        <IconButton
          size="7"
          onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}
        >
          <ChevronLeft className="size-4" />
        </IconButton>
        <span className="text-[13px] font-semibold capitalize text-foreground">{monthLabel}</span>
        <IconButton
          size="7"
          onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}
        >
          <ChevronRight className="size-4" />
        </IconButton>
      </div>

      <div className="mt-2 grid grid-cols-7 place-items-center gap-y-1">
        {weekdayLabels.map((label, index) => (
          <span
            key={`${label}-${index}`}
            className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {label}
          </span>
        ))}
        {days.map((day) => {
          const iso = toIsoDate(day);
          const isCurrentMonth = day.getMonth() === viewDate.getMonth();
          const isSelected = iso === value || (isRange && iso === rangeEnd);
          const isInRange = isRange && value !== "" && rangeEnd !== "" && iso > value && iso < rangeEnd;
          const isToday = iso === today;

          return (
            <button
              key={iso}
              type="button"
              onClick={() => onPick(iso)}
              className={`flex size-8 items-center justify-center rounded-full text-[12.5px] transition-colors ${
                isSelected
                  ? "bg-accent font-semibold text-primary"
                  : isInRange
                    ? "bg-accent/40 text-foreground"
                    : isCurrentMonth
                      ? "text-foreground hover:bg-white/[0.08]"
                      : "text-muted-foreground/50 hover:bg-white/[0.06]"
              } ${isToday && !isSelected ? "border-2 border-primary/40" : ""}`}
            >
              {day.getDate()}
            </button>
          );
        })}
      </div>
    </>
  );
}
