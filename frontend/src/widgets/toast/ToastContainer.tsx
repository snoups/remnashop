import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { dismissToast, useToasts } from "@shared/lib/toast";
import type { ToastVariant } from "@shared/lib/toast";

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
  const { t } = useTranslation();
  const toasts = useToasts();

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-80 flex-col gap-2">
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
              className="pointer-events-auto flex items-start gap-2.5 rounded-popover-item border border-white/[0.14] bg-popover/60 p-3.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
            >
              <Icon className={`size-[18px] shrink-0 ${VARIANT_COLOR[item.variant]}`} />
              <p className="flex-1 text-[13px] text-foreground">{item.message}</p>
              <button
                type="button"
                onClick={() => dismissToast(item.id)}
                aria-label={t("toast.close")}
                className="shrink-0 rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
