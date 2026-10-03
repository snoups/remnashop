import { AlertTriangle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";

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
      <DialogHeader
        icon={danger ? AlertTriangle : Icon}
        tone={danger ? "danger" : "glass"}
        title={title}
      />

      {message && (
        <p className="whitespace-pre-line px-5 pt-4 text-[13px] text-foreground/80">{message}</p>
      )}

      {children && <div className="px-5 pt-3">{children}</div>}

      <div className="flex gap-2 px-5 pb-5 pt-4">
        <Button
          variant="outline"
          className="flex-1"
          type="button"
          onClick={close}
        >
          {cancelLabel}
        </Button>
        <Button variant={danger ? "danger" : "accent"} className="flex-1" onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </>
  );
}
