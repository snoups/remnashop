import { Calendar, ChevronLeft, ChevronRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { bounceTap } from "@shared/lib/bounceState";
import { anchorFor, type PopoverAnchor } from "@shared/lib/popover-anchor";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { IconButton } from "@shared/ui/IconButton";
import { POPOVER_CLASS } from "@shared/ui/classes";
import { FIELD_SURFACE_CLASS } from "@shared/ui/TextInput";

// header + weekday row + 6 week rows, with padding
const CALENDAR_MAX_HEIGHT = 320;

interface DatePickerFieldProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  // form: inside a form, the same dark surface as TextInput; glass is for filters
  variant?: "glass" | "form";
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

export function DatePickerField({ id, value, onChange, placeholder, variant = "glass" }: DatePickerFieldProps) {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  // portalled like SelectDropdown's popover: nested in the layout panel, its
  // backdrop-blur would only see that panel, not the page behind it
  const [anchor, setAnchor] = useState<PopoverAnchor | null>(null);
  const selected = parseIsoDate(value);
  const [viewDate, setViewDate] = useState(selected ?? new Date());

  useEffect(() => {
    if (isOpen) setViewDate(parseIsoDate(value) ?? new Date());
  }, [isOpen, value]);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const toggleOpen = () => {
    const trigger = triggerRef.current?.getBoundingClientRect();
    if (!isOpen && trigger) setAnchor(anchorFor(trigger, CALENDAR_MAX_HEIGHT));
    setIsOpen(!isOpen);
  };

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
        ref={triggerRef}
        id={id}
        tabIndex={0}
        onClick={toggleOpen}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleOpen();
          }
        }}
        {...bounceTap(0.04)}
        className={`group flex w-full cursor-pointer items-center rounded-full ${variant === "form" ? FIELD_SURFACE_CLASS : "border border-glass-border bg-white/[0.03] backdrop-blur-md transition-colors hover:bg-white/[0.06]"} py-2 pl-9 pr-8 text-sm font-medium text-foreground outline-none focus:border-primary`}
      >
        <Calendar className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
        <span className={displayValue ? "text-foreground" : "text-muted-foreground"}>
          {displayValue || placeholder}
        </span>
        {value && (
          <IconButton size="5" className="absolute right-2 top-1/2 -translate-y-1/2"
            onClick={(event) => {
              event.stopPropagation();
              onChange("");
            }}
          >
            <X className="size-3" />
          </IconButton>
        )}
      </motion.div>

      {createPortal(
        <AnimatePresence>
          {isOpen && anchor && (
            <motion.div
              ref={popoverRef}
              initial={{ opacity: 0, scale: 0.96, y: -4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -4 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              // calendar keeps its own w-64, not the trigger's width
              style={{ transformOrigin: "top" in anchor ? "top" : "bottom", ...anchor, width: undefined }}
              // z above Modal's z-50, same as SelectDropdown
              className={`${POPOVER_CLASS} fixed z-[60] w-64 p-3`}
            >
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
                      } ${isToday && !isSelected ? "border-2 border-primary/40" : ""}`}
                    >
                      {day.getDate()}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </div>
  );
}
