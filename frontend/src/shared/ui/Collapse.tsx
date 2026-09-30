import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

import { COLLAPSE_MOTION } from "@shared/ui/collapse-motion";

interface CollapseProps {
  open: boolean;
  className?: string;
  children: ReactNode;
}

export function Collapse({ open, className, children }: CollapseProps) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div {...COLLAPSE_MOTION}>
          <div className={className}>{children}</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
