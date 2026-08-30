import { Check, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ComponentType } from "react";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";

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
}

export function SelectDropdown({ id, value, options, placeholder, onChange, icon: Icon }: SelectDropdownProps) {
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const selectedLabel = options.find((option) => option.value === value)?.label ?? placeholder;

  return (
    <div ref={ref} className="relative">
      <motion.button
        id={id}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        {...bounceTap(bounceStrength)}
        className="group flex w-full items-center rounded-xl border border-border bg-input/60 py-2 pl-9 pr-8 text-left text-sm text-foreground outline-none transition-colors focus:border-primary"
      >
        <Icon className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus:group-hover:text-foreground group-focus:text-primary" />
        <span className="truncate">{selectedLabel}</span>
        <ChevronDown
          className={`pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors transition-transform group-not-focus:group-hover:text-foreground group-focus:text-primary ${isOpen ? "rotate-180" : ""}`}
        />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{ transformOrigin: "top" }}
            role="listbox"
            className="absolute left-0 top-full z-30 mt-2 w-full min-w-40 rounded-popover border border-white/[0.14] bg-popover/60 p-1.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={option.value === value}
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-popover-item px-2.5 py-2 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
              >
                <span className="truncate">{option.label}</span>
                {option.value === value && <Check className="size-3.5 shrink-0 text-primary" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
