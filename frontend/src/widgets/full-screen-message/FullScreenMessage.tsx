import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

export const FULL_SCREEN_ACTION_CLASS =
  "mt-2 inline-flex h-9 items-center rounded-full border border-transparent bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary-hover";

interface FullScreenMessageProps {
  icon: LucideIcon;
  /** text-primary for "nothing here", text-error for failures */
  iconClassName: string;
  code?: string;
  title: string;
  description: string;
  action: ReactNode;
}

// Standalone screen outside the dashboard chrome: 404 and the server-error screens.
export function FullScreenMessage({ icon: Icon, iconClassName, code, title, description, action }: FullScreenMessageProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-glass-border bg-surface/40 p-8 text-center shadow-2xl backdrop-blur-xl">
        <Icon className={`size-12 shrink-0 ${iconClassName}`} />
        <div>
          {code && <span className="font-mono text-3xl font-bold tracking-tight text-foreground">{code}</span>}
          <h1 className={`${code ? "mt-1 " : ""}text-lg font-bold text-foreground`}>{title}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
    </div>
  );
}
