import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { HexColorPicker } from "react-colorful";

import { useClickOutside } from "@shared/lib/use-click-outside";

interface ColorPickerFieldProps {
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  // What the closed swatch button shows, if different from the raw value
  // being edited -- e.g. previewing a hue rotation applied on top of the
  // stored color. The picker popover itself still edits `value` untouched,
  // so opening it never shows a rotated color as if it were the real one.
  displayValue?: string;
}

export function ColorPickerField({ value, onChange, ariaLabel, displayValue }: ColorPickerFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useClickOutside(ref, isOpen, () => setIsOpen(false));

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={ariaLabel}
        style={{ backgroundColor: displayValue ?? value }}
        className="size-9 shrink-0 rounded-full border-2 border-glass-border shadow-inner transition-transform hover:scale-105"
      />

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{ transformOrigin: "top" }}
            className="absolute left-0 top-full z-30 mt-2 w-fit rounded-popover border border-white/[0.14] bg-popover/60 p-3 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <HexColorPicker color={value} onChange={onChange} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
