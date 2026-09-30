import { Check, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useId, useRef, useState, type ComponentType, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { anchorFor, type PopoverAnchor } from "@shared/lib/popover-anchor";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { POPOVER_CLASS } from "@shared/ui/classes";
import { FIELD_SURFACE_CLASS } from "@shared/ui/TextInput";

const POPOVER_MAX_HEIGHT = 288;

export interface SelectOption {
  value: string;
  label: string;
  icon?: ComponentType<{ className?: string }>;
}

interface SelectDropdownProps {
  id?: string;
  value: string;
  options: SelectOption[];
  placeholder: string;
  onChange: (value: string) => void;
  icon: ComponentType<{ className?: string }>;
  disabled?: boolean;
  // compact: the dialog editor's panels -- 36px, the height of its PillTabs
  size?: "default" | "compact";
  // form: inside a form, the same dark surface as TextInput; glass is for filters
  variant?: "glass" | "form";
}

export function SelectDropdown({
  id,
  value,
  options,
  placeholder,
  onChange,
  icon: Icon,
  disabled = false,
  size = "default",
  variant = "glass",
}: SelectDropdownProps) {
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  // Portalled to the body and positioned from the trigger's own rect: panels
  // and dialogs clip their overflow, so an in-flow popover gets cut off.
  // measured on open only -- reposition on scroll if that shows.
  const [anchor, setAnchor] = useState<PopoverAnchor | null>(null);
  const baseId = useId();
  const optionId = (index: number) => `${baseId}-option-${index}`;

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const selectedOption = options.find((option) => option.value === value);
  const selectedLabel = selectedOption?.label ?? placeholder;
  const TriggerIcon = selectedOption?.icon ?? Icon;

  const toggleOpen = () => {
    setIsOpen((open) => {
      const next = !open;
      if (next) {
        const trigger = triggerRef.current?.getBoundingClientRect();
        if (trigger) setAnchor(anchorFor(trigger, POPOVER_MAX_HEIGHT));
        setActiveIndex(Math.max(options.findIndex((option) => option.value === value), 0));
      }
      return next;
    });
  };

  const selectIndex = (index: number) => {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    setIsOpen(false);
  };

  const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setActiveIndex(Math.max(options.findIndex((option) => option.value === value), 0));
        } else {
          const delta = event.key === "ArrowDown" ? 1 : -1;
          setActiveIndex((i) => Math.min(Math.max(i + delta, 0), options.length - 1));
        }
        break;
      }
      case "Home": {
        if (isOpen) {
          event.preventDefault();
          setActiveIndex(0);
        }
        break;
      }
      case "End": {
        if (isOpen) {
          event.preventDefault();
          setActiveIndex(options.length - 1);
        }
        break;
      }
      case "Enter":
      case " ": {
        if (isOpen && activeIndex >= 0) {
          event.preventDefault();
          selectIndex(activeIndex);
        }
        break;
      }
      case "Escape": {
        if (isOpen) {
          event.preventDefault();
          setIsOpen(false);
        }
        break;
      }
    }
  };

  return (
    <div ref={ref} className="relative">
      <motion.button
        ref={triggerRef}
        id={id}
        type="button"
        onClick={toggleOpen}
        onKeyDown={handleTriggerKeyDown}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-activedescendant={isOpen && activeIndex >= 0 ? optionId(activeIndex) : undefined}
        {...bounceTap(bounceStrength, 0.04)}
        className={`group flex w-full items-center rounded-full ${variant === "form" ? FIELD_SURFACE_CLASS : "border border-glass-border bg-white/[0.03] backdrop-blur-md transition-colors hover:bg-white/[0.06]"} pl-9 pr-8 text-left ${size === "compact" ? "h-9 text-[13px]" : "py-2 text-sm"} font-medium text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <TriggerIcon className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
        <span className="truncate">{selectedLabel}</span>
        <ChevronDown
          className={`pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors transition-transform group-not-focus:group-hover:text-foreground group-focus:text-primary ${isOpen ? "rotate-180" : ""}`}
        />
      </motion.button>

      {createPortal(
        <AnimatePresence>
          {isOpen && anchor && (
            <motion.div
              ref={popoverRef}
              initial={{ opacity: 0, scale: 0.96, y: -4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -4 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              style={{ transformOrigin: "top" in anchor ? "top" : "bottom", ...anchor }}
              role="listbox"
              id={`${baseId}-listbox`}
              onKeyDown={(event) => event.key === "Escape" && setIsOpen(false)}
              // z above Modal's own z-50: the popover lives in the body, so a
              // select inside a dialog still draws over it.
              className={`${POPOVER_CLASS} fixed z-[60] min-w-40 p-1.5`}
            >
              {/* the scroll lives inside the padding -- on the popover itself
                  the scrollbar column paints over the rounded corners */}
              <div className="max-h-72 overflow-y-auto">
                {options.map((option, index) => (
                  <motion.button
                    key={option.value}
                    id={optionId(index)}
                    type="button"
                    role="option"
                    aria-selected={option.value === value}
                    onClick={() => selectIndex(index)}
                    onMouseEnter={() => setActiveIndex(index)}
                    initial="rest"
                    animate={index === activeIndex ? "hover" : "rest"}
                    className={`flex h-9 w-full items-center justify-between gap-2 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07] ${index === activeIndex ? "bg-white/[0.07]" : ""}`}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      {option.icon && (
                        <BounceIcon icon={option.icon} size={14} hoverSize={17} className="text-muted-foreground" />
                      )}
                      <span className="truncate">{option.label}</span>
                    </span>
                    {option.value === value && <Check className="size-3.5 shrink-0 text-primary" />}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </div>
  );
}
