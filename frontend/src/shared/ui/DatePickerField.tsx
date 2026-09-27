import { Calendar, ChevronLeft, ChevronRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";

interface DatePickerFieldProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  clearAriaLabel: string;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
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

export function DatePickerField({ id, value, onChange, placeholder, clearAriaLabel }: DatePickerFieldProps) {
  const { i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = parseIsoDate(value);
  const [viewDate, setViewDate] = useState(selected ?? new Date());

  useEffect(() => {
    if (isOpen) setViewDate(parseIsoDate(value) ?? new Date());
  }, [isOpen, value]);

  useClickOutside(ref, isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, ref, () => setIsOpen(false));

  const today = new Date();
  const days = getMonthGrid(viewDate.getFullYear(), viewDate.getMonth());
  const monthLabel = viewDate.toLocaleDateString(i18n.language, { month: "long", year: "numeric" });
  const weekdayLabels = Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 1 + i).toLocaleDateString(i18n.language, { weekday: "short" }),
  );
  const displayValue = selected ? selected.toLocaleDateString(i18n.language) : "";

  return (
    <div ref={ref} className="relative">
      <motion.div
        id={id}
        role="button"
        tabIndex={0}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setIsOpen((open) => !open);
          }
        }}
        {...bounceTap(bounceStrength)}
        className="group flex w-full cursor-pointer items-center rounded-xl border border-border bg-input/60 py-2 pl-9 pr-8 text-sm text-foreground outline-none transition-colors focus:border-primary"
      >
        <Calendar className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
        <span className={displayValue ? "text-foreground" : "text-muted-foreground"}>
          {displayValue || placeholder}
        </span>
        {value && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onChange("");
            }}
            aria-label={clearAriaLabel}
            className="absolute right-2 top-1/2 flex size-5 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.1] hover:text-foreground"
          >
            <X className="size-3" />
          </button>
        )}
      </motion.div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{ transformOrigin: "top" }}
            className="absolute left-0 top-full z-30 mt-2 w-64 rounded-popover border border-white/[0.14] bg-popover/60 p-3 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}
                className="flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
              >
                <ChevronLeft className="size-4" />
              </button>
              <span className="text-[13px] font-semibold capitalize text-foreground">{monthLabel}</span>
              <button
                type="button"
                onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}
                className="flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
              >
                <ChevronRight className="size-4" />
              </button>
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
                const isCurrentMonth = day.getMonth() === viewDate.getMonth();
                const isSelected = selected !== null && toIsoDate(day) === toIsoDate(selected);
                const isToday = toIsoDate(day) === toIsoDate(today);

                return (
                  <button
                    key={toIsoDate(day)}
                    type="button"
                    onClick={() => {
                      onChange(toIsoDate(day));
                      setIsOpen(false);
                    }}
                    className={`flex size-8 items-center justify-center rounded-full text-[12.5px] transition-colors ${
                      isSelected
                        ? "bg-accent font-semibold text-primary"
                        : isCurrentMonth
                          ? "text-foreground hover:bg-white/[0.08]"
                          : "text-muted-foreground/50 hover:bg-white/[0.06]"
                    } ${isToday && !isSelected ? "border border-primary/40" : ""}`}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
