import { AlertTriangle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Modal } from "@shared/ui/Modal";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";

interface ConfirmDialogProps {
  title: string;
  message?: string;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  size?: "sm" | "md" | "lg";
  /** header icon for a non-danger dialog; danger always shows the warning icon */
  icon?: LucideIcon;
  /** false renders inline in the parent's container instead of portaling to document.body */
  portal?: boolean;
  /** extra content between the message and the buttons: a diff table, a small form */
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
  const close = useModalClose();

  return (
    <>
      <DialogHeader icon={danger ? AlertTriangle : Icon} danger={danger} title={title} />

      {(message || children) && (
        <div className="flex flex-col gap-3 p-4">
          {message && <p className="whitespace-pre-line text-[13px] text-foreground/80">{message}</p>}
          {children}
        </div>
      )}

      <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
        <Button variant="glass" onClick={close}>
          {cancelLabel}
        </Button>
        <Button variant={danger ? "glassDanger" : "glassAccent"} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </>
  );
}
