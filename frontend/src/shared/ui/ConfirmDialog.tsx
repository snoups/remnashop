import { AlertTriangle, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  /** false renders inline in the parent's own container instead of portaling to document.body */
  portal?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger,
  portal = true,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const dialog = (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
      >
        <button
          type="button"
          aria-hidden
          tabIndex={-1}
          className="absolute inset-0 cursor-default"
          onClick={onCancel}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
        >
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
              {danger && (
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-error/30 bg-error/10 text-error">
                  <AlertTriangle className="size-4" />
                </div>
              )}
              {title}
            </h2>
            <button
              type="button"
              onClick={onCancel}
              aria-label={t("profile.edit.close")}
              className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>

          <p className="px-5 pt-4 text-[12.5px] text-muted-foreground">{message}</p>

          <div className="flex gap-2 px-5 pb-5 pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
            >
              {cancelLabel}
            </button>
            <motion.button
              type="button"
              onClick={onConfirm}
              {...bounceTap(bounceStrength)}
              className={
                danger
                  ? "flex-1 rounded-full border border-error/30 bg-error/10 px-4 py-2 text-sm font-medium text-error transition-colors hover:bg-error/20"
                  : "flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
              }
            >
              {confirmLabel}
            </motion.button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );

  return portal ? createPortal(dialog, document.body) : dialog;
}
