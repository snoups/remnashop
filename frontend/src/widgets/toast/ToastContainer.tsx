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
    // above dialogs (z-50), below FieldHint (z-100)
    <div className="pointer-events-none fixed right-4 top-3 z-[90] flex w-80 flex-col gap-2 min-[1792px]:w-[min(20rem,50vw_-_41rem)]">
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
              // move too: a toast that appears under a still pointer gets no enter until it moves
              onPointerEnter={() => pauseToast(item.id)}
              onPointerMove={() => pauseToast(item.id)}
              onPointerLeave={() => resumeToast(item.id)}
              // one line is 48px (a 32px row 8px in): a single-line toast is a pill with the close button on its curve
              className="glass-dialog pointer-events-auto flex items-start gap-3 rounded-[32px] p-2 pl-4"
            >
              <Icon className={`mt-[7px] size-[18px] shrink-0 ${VARIANT_COLOR[item.variant]}`} />
              <p className="flex-1 py-1 text-[13px] leading-6 text-foreground">{item.message}</p>
              <IconButton size="8" onClick={() => dismissToast(item.id)}>
                <X className="size-3.5" />
              </IconButton>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
