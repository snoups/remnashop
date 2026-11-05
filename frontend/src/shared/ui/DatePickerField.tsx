import { Calendar, X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { parseIsoDate } from "@shared/lib/iso-date";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { IconButton } from "@shared/ui/IconButton";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { PICKER_ICON_CLASS } from "@shared/ui/classes";

const SURFACE_CLASS = {
  glass: "border border-glass-border bg-white/[0.03] backdrop-blur-md transition-colors hover:bg-white/[0.06]",
  well: "glass-well ring-inset focus:ring-1 focus:ring-primary",
} as const;

// header + weekday row + 6 week rows, with padding
const CALENDAR_MAX_HEIGHT = 320;

interface DatePickerFieldProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  // glass is for filters; well: a glass dialog's form, the sunken well of its Input
  variant?: "glass" | "well";
  /** 36px, 13px text and a glass popover: the glass design's filter row */
  compact?: boolean;
}

export function DatePickerField({ id, value, onChange, placeholder, variant = "glass", compact = false }: DatePickerFieldProps) {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const selected = parseIsoDate(value);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const toggleOpen = () => setIsOpen(!isOpen);

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
        className={`group flex w-full cursor-pointer items-center rounded-full ${SURFACE_CLASS[variant]} ${compact ? "h-9 text-[13px]" : "py-2 text-sm"} pl-9 pr-8 ${variant === "well" ? "" : "font-medium"} text-foreground outline-none focus:border-primary`}
      >
        <Calendar className={PICKER_ICON_CLASS} />
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

      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="left"
        maxHeight={CALENDAR_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        glass={compact || variant === "well"}
        className="w-64 p-3"
>
        <MonthCalendar
          value={value}
          onPick={(isoDate) => {
            onChange(isoDate);
            setIsOpen(false);
          }}
        />
      </PortalPopover>
    </div>
  );
}
