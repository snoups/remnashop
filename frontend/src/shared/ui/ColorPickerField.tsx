import { useRef, useState } from "react";
import { HexColorPicker } from "react-colorful";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Ripple } from "@shared/ui/Ripple";

// HexColorPicker (200px) plus the popover padding
const POPOVER_MAX_HEIGHT = 230;

interface ColorPickerFieldProps {
  value: string;
  onChange: (value: string) => void;
  // what the closed swatch shows when it differs from the edited value (a hue
  // rotation preview); the popover still edits the untouched `value`
  displayValue?: string;
}

export function ColorPickerField({ value, onChange, displayValue }: ColorPickerFieldProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  return (
    <div ref={ref} className="relative flex">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        style={{ backgroundColor: displayValue ?? value }}
        className="relative size-9 shrink-0 rounded-full border-2 border-glass-border shadow-inner"
      >
        <Ripple />
      </button>

      <PortalPopover
        glass
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align="left"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-fit p-3"
      >
        <HexColorPicker color={value} onChange={onChange} />
      </PortalPopover>
    </div>
  );
}
