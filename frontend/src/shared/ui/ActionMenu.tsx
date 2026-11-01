import { ChevronDown, MoreVertical } from "lucide-react";
import { motion } from "motion/react";
import { Fragment, useRef, useState, type ComponentType } from "react";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Tooltip } from "@shared/ui/Tooltip";
import { Ripple } from "@shared/ui/Ripple";

// separators aside: 36px per item plus the popover padding
const ITEM_HEIGHT = 36;

export interface ActionMenuItem {
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick: () => void;
  variant?: "danger";
  separatorBefore?: boolean;
  disabled?: boolean;
  /** why the item is disabled; shown on hover */
  hint?: string;
}

interface ActionMenuProps {
  items: ActionMenuItem[];
  /** a labelled button instead of the ⋮ icon, e.g. in a dialog footer */
  trigger?: { label: string; icon: ComponentType<{ className?: string }> };
}

export function ActionMenu({ items, trigger }: ActionMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  if (items.length === 0) return null;

  return (
    <div ref={ref} className="relative">
      {trigger ? (
        <Button variant="outline" onClick={() => setIsOpen((open) => !open)} aria-expanded={isOpen}>
          <trigger.icon className="size-3.5" />
          {trigger.label}
          <ChevronDown className={`size-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
        </Button>
      ) : (
        <IconButton
          size="8"
          onClick={() => setIsOpen((open) => !open)}
          aria-expanded={isOpen}
          propagate={{ tap: false }}
        >
          <MoreVertical className="size-4" />
        </IconButton>
      )}

      <PortalPopover
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align="right"
        maxHeight={items.length * ITEM_HEIGHT + 20}
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.85 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        tabIndex={-1}
        className="min-w-44 outline-none p-1.5"
      >
        {items.map((item, index) => (
          <Fragment key={item.label}>
            {item.separatorBefore && index > 0 && (
              <div className="my-1 h-px bg-white/[0.08]" />
            )}
            {/* the wrapper carries the hover: a disabled button doesn't reliably get one */}
            <div className="group relative">
              <motion.button
                type="button"
                disabled={item.disabled}
                onClick={() => {
                  setIsOpen(false);
                  item.onClick();
                }}
                className={`relative flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium transition-colors enabled:hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-50 ${
                  item.variant === "danger" ? "text-error" : "text-foreground"
                }`}
              >
                <Ripple />
                <item.icon className="size-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </motion.button>
              {item.hint && <Tooltip text={item.hint} side="top" />}
            </div>
          </Fragment>
        ))}
      </PortalPopover>
    </div>
  );
}
