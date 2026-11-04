import { SmilePlus } from "lucide-react";
import { lazy, Suspense, useRef, useState } from "react";

import type { PlanIconValue } from "@entities/plans/api";
import { PlanIcon } from "@entities/plans/PlanIcon";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Spinner } from "@shared/ui/Spinner";

const PlanIconPickerBody = lazy(() =>
  import("@features/plan-edit/PlanIconPickerBody").then((module) => ({ default: module.PlanIconPickerBody })),
);

const POPOVER_MAX_HEIGHT = 380;

/** A 28px button at the end of the name field; the popover offers the imported emoji packs. */
export function PlanIconPicker({ value, onChange }: { value: PlanIconValue; onChange: (value: PlanIconValue) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  useClickOutside<HTMLElement>([triggerRef, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll<HTMLElement>(isOpen, popoverRef, () => setIsOpen(false));

  return (
    <>
      <IconButton ref={triggerRef} size="7" onClick={() => setIsOpen((open) => !open)}>
        <PlanIcon icon={value} size={16} fallback={<SmilePlus className="size-4" />} />
      </IconButton>
      <PortalPopover
        glass
        solid
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-80 p-1.5"
      >
        <Suspense fallback={<Spinner size="card" />}>
          <PlanIconPickerBody
            value={value}
            onChange={(next) => {
              onChange(next);
              setIsOpen(false);
            }}
          />
        </Suspense>
      </PortalPopover>
    </>
  );
}
