import { CalendarClock, Clock, X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PICKER_ICON_CLASS } from "@shared/ui/classes";
import { Input } from "@shared/ui/glass/Input";
import { IconButton } from "@shared/ui/IconButton";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { PortalPopover } from "@shared/ui/PortalPopover";

// header + weekday row + 6 week rows, the time row under them, with padding
const POPOVER_MAX_HEIGHT = 380;

// a date picked with no time yet: the next full hour
function nextHour(): string {
  const hour = (new Date().getHours() + 1) % 24;
  return `${String(hour).padStart(2, "0")}:00`;
}

/** A local date and time as <input type="datetime-local"> holds it ("2026-10-08T18:30", "" for none),
 *  picked on the app's calendar: the glass filter field's look, 36px, a glass popover. */
export function DateTimePickerField({
  value,
  onChange,
  placeholder,
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  /** layout only (a width) */
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [date = "", time = ""] = value.split("T");
  // what's typed, kept until it is a whole HH:MM; synced back when the value changes elsewhere
  const [timeDraft, setTimeDraft] = useState(time);
  const [syncedTime, setSyncedTime] = useState(time);
  if (time !== syncedTime) {
    setSyncedTime(time);
    setTimeDraft(time);
  }

  const typeTime = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, 4);
    const next = digits.length > 2 ? `${digits.slice(0, 2)}:${digits.slice(2)}` : digits;
    setTimeDraft(next);
    const match = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(next);
    if (match && date) onChange(`${date}T${next}`);
  };

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const display = value
    ? new Date(value).toLocaleString(i18n.language, { dateStyle: "short", timeStyle: "short" })
    : "";
  const toggleOpen = () => setIsOpen((open) => !open);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <motion.div
        ref={triggerRef}
        tabIndex={0}
        onClick={toggleOpen}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleOpen();
          }
        }}
        className="group flex h-9 w-full cursor-pointer items-center rounded-full border border-glass-border bg-white/[0.03] pl-9 pr-8 text-[13px] font-medium backdrop-blur-md outline-none transition-colors hover:bg-white/[0.06] focus:border-primary"
      >
        <CalendarClock className={PICKER_ICON_CLASS} />
        <span className={`truncate ${display ? "text-foreground" : "text-muted-foreground"}`}>{display || placeholder}</span>
        {value && (
          <IconButton
            size="5"
            className="absolute right-2 top-1/2 -translate-y-1/2"
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
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        glass
        className="flex w-64 flex-col gap-3 p-3"
      >
        <MonthCalendar value={date} onPick={(picked) => onChange(`${picked}T${time || nextHour()}`)} />
        <label className="flex items-center gap-2 border-t border-white/[0.08] pt-3">
          <Clock className="size-3.5 text-muted-foreground" />
          <span className="flex-1 text-[13px] text-muted-foreground">{t("common.time")}</span>
          {/* plain text, not type="time": no browser picker of its own */}
          <Input
            type="text"
            inputMode="numeric"
            placeholder={t("common.timePlaceholder")}
            value={timeDraft}
            disabled={!date}
            onChange={(event) => typeTime(event.target.value)}
            onBlur={() => setTimeDraft(time)}
            className="w-24"
          />
        </label>
      </PortalPopover>
    </div>
  );
}
