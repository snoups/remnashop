import type { ComponentType } from "react";

import { FieldHint } from "@shared/ui/FieldHint";

export function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl border border-border bg-surface/40 p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
        {hint && <FieldHint text={hint} />}
      </div>
      <span className="text-2xl font-bold text-foreground">{value}</span>
    </div>
  );
}
