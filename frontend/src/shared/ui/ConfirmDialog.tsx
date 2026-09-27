import { AlertTriangle, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface ConfirmDialogProps {
  title: string;
  message?: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  size?: "sm" | "md" | "lg";
  /** header icon for a non-danger dialog; danger always shows the warning icon */
  icon?: LucideIcon;
  /** false renders inline in the parent's own container instead of portaling to document.body */
  portal?: boolean;
  /** extra content rendered between the message and the action buttons -- a diff table, a small form, etc. */
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger,
  size = "sm",
  icon,
  portal = true,
  children,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal onClose={onCancel} size={size} portal={portal}>
      <ConfirmDialogBody
        title={title}
        message={message}
        confirmLabel={confirmLabel}
        cancelLabel={cancelLabel}
        danger={danger}
        icon={icon}
        onConfirm={onConfirm}
      >
        {children}
      </ConfirmDialogBody>
    </Modal>
  );
}

function ConfirmDialogBody({
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger,
  icon: Icon,
  children,
  onConfirm,
}: Omit<ConfirmDialogProps, "portal" | "onCancel" | "size">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          {(danger || Icon) && (
            <div
              className={
                danger
                  ? "flex size-8 shrink-0 items-center justify-center rounded-full border border-error/30 bg-error/10 text-error"
                  : "flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md"
              }
            >
              {danger ? <AlertTriangle className="size-4" /> : Icon && <Icon className="size-4" />}
            </div>
          )}
          {title}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {message && (
        <p className="whitespace-pre-line px-5 pt-4 text-[12.5px] text-muted-foreground">{message}</p>
      )}

      {children && <div className="px-5 pt-3">{children}</div>}

      <div className="flex gap-2 px-5 pb-5 pt-4">
        <button
          type="button"
          onClick={close}
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
    </>
  );
}
