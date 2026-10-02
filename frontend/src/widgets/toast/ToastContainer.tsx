import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ComponentType } from "react";

import { dismissToast, pauseToast, resumeToast, useToasts } from "@shared/lib/toast";
import type { ToastVariant } from "@shared/lib/toast";
import { IconButton } from "@shared/ui/IconButton";

const VARIANT_ICON: Record<ToastVariant, ComponentType<{ className?: string }>> = {
  error: AlertCircle,
  warning: AlertTriangle,
  success: CheckCircle2,
  info: Info,
};

const VARIANT_COLOR: Record<ToastVariant, string> = {
  error: "text-error",
  warning: "text-warning",
  success: "text-success",
  info: "text-primary",
};

export function ToastContainer() {
  const toasts = useToasts();

  return (
    <div className="pointer-events-none fixed right-4 top-3 z-50 flex w-80 flex-col gap-2 min-[1792px]:w-[min(20rem,50vw_-_41rem)]">
      <AnimatePresence>
        {toasts.map((item) => {
          const Icon = VARIANT_ICON[item.variant];
          return (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, y: -12, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              onMouseEnter={() => pauseToast(item.id)}
              onMouseLeave={() => resumeToast(item.id)}
              // solid while the toast overlaps page content; from 1792px it sits in
              // the empty gutter beside the content (see the width above), so glass reads fine
              className="pointer-events-auto flex items-start gap-2.5 rounded-popover-item border border-white/[0.14] bg-popover p-3.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] min-[1792px]:bg-popover/60 min-[1792px]:backdrop-blur-2xl min-[1792px]:backdrop-saturate-150"
            >
              <Icon className={`mt-[3px] size-[18px] shrink-0 ${VARIANT_COLOR[item.variant]}`} />
              <p className="flex-1 text-[13px] leading-6 text-foreground">{item.message}</p>
              <IconButton size="8" className="-my-1 -mr-1"
                onClick={() => dismissToast(item.id)}
              >
                <X className="size-4" />
              </IconButton>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
