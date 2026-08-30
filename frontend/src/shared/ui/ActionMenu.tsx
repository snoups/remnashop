import { MoreVertical } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ComponentType } from "react";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BounceIcon } from "@shared/ui/BounceIcon";

export interface ActionMenuItem {
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick: () => void;
  variant?: "danger";
}

interface ActionMenuProps {
  items: ActionMenuItem[];
}

export function ActionMenu({ items }: ActionMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const bounceStrength = useBounceStrength();

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  if (items.length === 0) return null;

  return (
    <div ref={ref} className="relative">
      <motion.button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        {...bounceTap(bounceStrength, 0.12)}
        className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
      >
        <MoreVertical className="size-4" />
      </motion.button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{ transformOrigin: "top right" }}
            role="menu"
            className="absolute right-0 top-full z-30 mt-2 min-w-44 rounded-popover border border-white/[0.14] bg-popover/60 p-1.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            {items.map((item) => (
              <motion.button
                key={item.label}
                type="button"
                role="menuitem"
                onClick={() => {
                  setIsOpen(false);
                  item.onClick();
                }}
                initial="rest"
                whileHover="hover"
                className={`flex w-full items-center gap-2.5 rounded-full px-2.5 py-2 text-left text-[13px] font-medium transition-colors hover:bg-white/[0.07] ${
                  item.variant === "danger" ? "text-error" : "text-foreground"
                }`}
              >
                <BounceIcon icon={item.icon} size={15} hoverSize={18.75} />
                <span className="truncate">{item.label}</span>
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
