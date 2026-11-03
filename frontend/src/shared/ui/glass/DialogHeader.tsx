import { X } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { IconCircle } from "@shared/ui/glass/IconCircle";
import { IconButton } from "@shared/ui/IconButton";
import { useModalClose } from "@shared/ui/modal-hooks";

/** Header of a Modal material="glass": icon, 15px title, actions, close (through the modal's exit). */
export function DialogHeader({
  icon,
  glyph,
  title,
  actions,
  closable = true,
  danger = false,
  warning = false,
}: {
  icon?: ComponentType<{ className?: string }>;
  /** the circle's content instead of an icon: an emoji */
  glyph?: ReactNode;
  title: string;
  /** before the close button: a refresh, a spinner; 36px tall like the header icon */
  actions?: ReactNode;
  /** false: no close button, for a dialog only its own action may close */
  closable?: boolean;
  /** the icon in the error tone */
  danger?: boolean;
  /** the icon in the warning tone */
  warning?: boolean;
}) {
  const close = useModalClose();
  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-white/[0.08] p-4">
      {(icon || glyph) && <IconCircle icon={icon} glyph={glyph} header danger={danger} warning={warning} />}
      <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      {/* 36px, the header icon's height: every control in a header is */}
      {closable && (
        <IconButton size="9" onClick={close}>
          <X className="size-4" />
        </IconButton>
      )}
    </div>
  );
}
