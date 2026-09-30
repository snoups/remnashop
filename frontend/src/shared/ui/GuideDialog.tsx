import { CircleHelp } from "lucide-react";
import { useState, type ReactNode } from "react";

import { DialogHeader } from "@shared/ui/DialogHeader";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";

interface GuideDialogProps {
  ariaLabel: string;
  title: string;
  children: ReactNode;
}

export function GuideDialog({ ariaLabel, title, children }: GuideDialogProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <IconButton size="6"
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen(true);
        }}
        aria-label={ariaLabel}
      >
        <CircleHelp className="size-4" />
      </IconButton>

      {isOpen && (
        // the trigger sits inside clickable rows; portal events still bubble through the React tree
        <span className="contents" onClick={(event) => event.stopPropagation()}>
          <Modal onClose={() => setIsOpen(false)} size="lg" scrollable>
            <DialogHeader icon={CircleHelp} title={title} />
            <div className="flex min-h-0 flex-col gap-5 overflow-y-auto px-5 py-4 text-sm text-foreground/90">
              {children}
            </div>
          </Modal>
        </span>
      )}
    </>
  );
}
