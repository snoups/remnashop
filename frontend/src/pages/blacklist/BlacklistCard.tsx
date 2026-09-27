import type { ComponentType, ReactNode } from "react";

import type { BlacklistKind } from "@entities/blacklist/api";

export function BlacklistCard({
  icon: Icon,
  title,
  description,
  action,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-foreground">{title}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />
      {children}
    </section>
  );
}

export function KindBadge({ kind, label }: { kind: BlacklistKind; label: string }) {
  return (
    <span
      className={`w-[84px] shrink-0 rounded-full py-0.5 text-center text-[10.5px] font-semibold uppercase tracking-wide ${
        kind === "TELEGRAM_ID" ? "bg-primary/10 text-accent-foreground" : "bg-white/[0.06] text-muted-foreground"
      }`}
    >
      {label}
    </span>
  );
}

export const inputClassName =
  "min-w-0 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";
