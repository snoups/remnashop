import { Calendar, X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap } from "@shared/lib/bounceState";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { parseIsoDate } from "@shared/lib/iso-date";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { IconButton } from "@shared/ui/IconButton";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { PortalPopover } from "@shared/ui/PortalPopover";
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

export function DatePickerField({ id, value, onChange, placeholder, variant = "glass" }: DatePickerFieldProps) {
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
