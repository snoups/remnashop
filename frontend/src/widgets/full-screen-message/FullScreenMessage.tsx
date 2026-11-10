import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { GLASS_STANDALONE_CARD_CLASS, SCREEN_TITLE_CLASS } from "@shared/ui/classes";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

// Button's glassSolid, full width: the card's one action
export const FULL_SCREEN_ACTION_CLASS =
  "flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-transparent bg-primary px-3.5 text-sm font-semibold text-primary-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] transition-colors hover:bg-primary-hover";

const TONE_CLASS = {
  primary:
    "border-primary/40 bg-accent text-primary shadow-[0_0_46px_color-mix(in_srgb,var(--color-primary)_28%,transparent)]",
  error:
    "border-error/40 bg-error/10 text-error shadow-[0_0_46px_color-mix(in_srgb,var(--color-error)_24%,transparent)]",
} as const;

interface FullScreenMessageProps {
  icon: LucideIcon;
  /** primary for "nothing here", error for failures */
  tone: keyof typeof TONE_CLASS;
  code?: string;
  title: string;
  description: string;
  action: ReactNode;
}

// Standalone screen outside the dashboard chrome: 404 and the error screens, on the sign-in page's glass.
export function FullScreenMessage({ icon: Icon, tone, code, title, description, action }: FullScreenMessageProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <div className={`flex w-full max-w-sm flex-col items-center gap-6 text-center ${GLASS_STANDALONE_CARD_CLASS}`}>
        <span className={`flex size-[72px] items-center justify-center rounded-full border ${TONE_CLASS[tone]}`}>
          <Icon className="size-8" />
        </span>
        <div className="flex flex-col gap-2">
          {code && <span className="font-mono text-[28px] font-bold tracking-tight text-foreground">{code}</span>}
          <h1 className={SCREEN_TITLE_CLASS}>{title}</h1>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
    </div>
  );
}
