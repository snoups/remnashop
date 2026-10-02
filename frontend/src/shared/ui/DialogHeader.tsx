import { X } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { useModalClose } from "@shared/ui/modal-hooks";
import { IconButton } from "@shared/ui/IconButton";

const TONE_CLASS = {
  glass: "border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md",
  primary: "bg-primary/10 text-primary",
  muted: "bg-white/[0.06] text-muted-foreground",
  danger: "border border-error/30 bg-error/10 text-error",
} as const;

interface DialogHeaderProps {
  title: ReactNode;
  /** lucide icon inside the circle */
  icon?: ComponentType<{ className?: string }>;
  /** custom circle content instead of an icon: initials, a currency symbol, an emoji */
  glyph?: ReactNode;
  tone?: keyof typeof TONE_CLASS;
  /** replaces the circle entirely (e.g. a back button) */
  leading?: ReactNode;
  /** inline after the title: status badges, a copy button */
  badges?: ReactNode;
  subtitle?: ReactNode;
  /** before the close button */
  actions?: ReactNode;
  /** defaults to the surrounding Modal's close; null hides the button */
  onClose?: (() => void) | null;
}

export function DialogHeader({
  title,
  icon: Icon,
  glyph,
  tone = "glass",
  leading,
  badges,
  subtitle,
  actions,
  onClose,
}: DialogHeaderProps) {
  const modalClose = useModalClose();
  const close = onClose === undefined ? modalClose : onClose;
  const hasCircle = Icon !== undefined || glyph !== undefined;

  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-border px-5 py-4">
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        {leading ||
          (hasCircle && (
            <div
              className={`flex size-8 shrink-0 items-center justify-center rounded-full ${TONE_CLASS[tone]}`}
            >
              {Icon ? <Icon className="size-4" /> : glyph}
            </div>
          ))}
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <h2 className="truncate text-base font-bold text-foreground">{title}</h2>
            {badges}
          </div>
          {subtitle && <div className="mt-0.5 truncate text-[12px] text-muted-foreground">{subtitle}</div>}
        </div>
      </div>
      {actions}
      {close && (
        <IconButton size="8"
          onClick={close}
        >
          <X className="size-4" />
        </IconButton>
      )}
    </div>
  );
}
