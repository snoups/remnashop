import { Check, ChevronDown } from "lucide-react";
import { motion } from "motion/react";
import { useId, useRef, useState, type ComponentType, type KeyboardEvent } from "react";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { FIELD_SURFACE_CLASS } from "@shared/ui/TextInput";
import { Ripple } from "@shared/ui/Ripple";

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
  // compact: the dialog editor's panels, 36px like its PillTabs; lg: 40px, next to DialogTabs
  size?: "default" | "compact" | "lg";
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
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const baseId = useId();
  const optionId = (index: number) => `${baseId}-option-${index}`;

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const selectedOption = options.find((option) => option.value === value);
  const selectedLabel = selectedOption?.label ?? placeholder;
  const TriggerIcon = selectedOption?.icon ?? Icon;

  const openMenu = () => {
    setActiveIndex(Math.max(options.findIndex((option) => option.value === value), 0));
    setIsOpen(true);
  };

  const toggleOpen = () => (isOpen ? setIsOpen(false) : openMenu());

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
          openMenu();
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
        className={`relative group flex w-full items-center rounded-full ${variant === "form" ? FIELD_SURFACE_CLASS : "border border-glass-border bg-white/[0.03] backdrop-blur-md transition-colors hover:bg-white/[0.06]"} pl-9 pr-8 text-left ${size === "compact" ? "h-9 text-[13px]" : size === "lg" ? "h-10 text-sm" : "py-2 text-sm"} font-medium text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <Ripple />
        <TriggerIcon className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
        <span className="truncate">{selectedLabel}</span>
        <ChevronDown
          className={`pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors transition-transform group-not-focus:group-hover:text-foreground group-focus:text-primary ${isOpen ? "rotate-180" : ""}`}
        />
      </motion.button>

      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="stretch"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        id={`${baseId}-listbox`}
        onKeyDown={(event) => event.key === "Escape" && setIsOpen(false)}
        className="min-w-40 p-1.5"
>
        {/* the scroll lives inside the padding: on the popover itself
            the scrollbar column paints over the rounded corners */}
        <div className="max-h-72 overflow-y-auto">
          {options.map((option, index) => (
            <motion.button
              key={option.value}
              id={optionId(index)}
              type="button"
              onClick={() => selectIndex(index)}
              onMouseEnter={() => setActiveIndex(index)}
              animate={index === activeIndex ? "hover" : "rest"}
              className={`relative flex h-9 w-full items-center justify-between gap-2 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07] ${index === activeIndex ? "bg-white/[0.07]" : ""}`}
            >
              <Ripple />
              <span className="flex min-w-0 items-center gap-2">
                {option.icon && (
                  <option.icon className="size-4 shrink-0 text-muted-foreground" />
                )}
                <span className="truncate">{option.label}</span>
              </span>
              {option.value === value && <Check className="size-3.5 shrink-0 text-primary" />}
            </motion.button>
          ))}
        </div>
      </PortalPopover>
    </div>
  );
}
