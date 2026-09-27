import { Check, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useId, useRef, useState, type ComponentType, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";

const POPOVER_MAX_HEIGHT = 288;
const POPOVER_GAP = 8;

type PopoverAnchor = { left: number; width: number } & ({ top: number } | { bottom: number });

function anchorFor(trigger: DOMRect): PopoverAnchor {
  const box = { left: trigger.left, width: trigger.width };
  return window.innerHeight - trigger.bottom < POPOVER_MAX_HEIGHT && trigger.top > POPOVER_MAX_HEIGHT
    ? { ...box, bottom: window.innerHeight - trigger.top + POPOVER_GAP }
    : { ...box, top: trigger.bottom + POPOVER_GAP };
}

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectDropdownProps {
  id?: string;
  value: string;
  options: SelectOption[];
  placeholder: string;
  onChange: (value: string) => void;
  icon: ComponentType<{ className?: string }>;
  disabled?: boolean;
}

export function SelectDropdown({
  id,
  value,
  options,
  placeholder,
  onChange,
  icon: Icon,
  disabled = false,
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

  const selectedLabel = options.find((option) => option.value === value)?.label ?? placeholder;

  const toggleOpen = () => {
    setIsOpen((open) => {
      const next = !open;
      if (next) {
        const trigger = triggerRef.current?.getBoundingClientRect();
        if (trigger) setAnchor(anchorFor(trigger));
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
        {...bounceTap(bounceStrength)}
        className="group flex w-full items-center rounded-xl border border-border bg-input/60 py-2 pl-9 pr-8 text-left text-sm text-foreground outline-none transition-colors focus:border-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Icon className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
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
              className="fixed z-[60] min-w-40 rounded-popover border border-white/[0.14] bg-popover/60 p-1.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
            >
              {/* the scroll lives inside the padding -- on the popover itself
                  the scrollbar column paints over the rounded corners */}
              <div className="max-h-72 overflow-y-auto">
                {options.map((option, index) => (
                  <button
                    key={option.value}
                    id={optionId(index)}
                    type="button"
                    role="option"
                    aria-selected={option.value === value}
                    onClick={() => selectIndex(index)}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={`flex w-full items-center justify-between gap-2 rounded-popover-item px-2.5 py-2 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07] ${index === activeIndex ? "bg-white/[0.07]" : ""}`}
                  >
                    <span className="truncate">{option.label}</span>
                    {option.value === value && <Check className="size-3.5 shrink-0 text-primary" />}
                  </button>
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
