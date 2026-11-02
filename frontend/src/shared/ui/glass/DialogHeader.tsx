import { X } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { IconCircle } from "@shared/ui/glass/IconCircle";
import { IconButton } from "@shared/ui/IconButton";
import { useModalClose } from "@shared/ui/modal-hooks";

/** Header of a Modal material="glass": icon, 15px title, actions, close (through the modal's exit). */
export function DialogHeader({
  icon,
  title,
  actions,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  /** before the close button: a refresh, a spinner; 36px tall like the header icon */
  actions?: ReactNode;
}) {
  const close = useModalClose();
  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-white/[0.08] px-5 py-4">
      <IconCircle icon={icon} header />
      <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      {/* 36px, the header icon's height: every control in a header is */}
      <IconButton size="9" onClick={close}>
        <X className="size-4" />
      </IconButton>
    </div>
  );
}
