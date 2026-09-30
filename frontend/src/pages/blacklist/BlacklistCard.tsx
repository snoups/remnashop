import type { ComponentType, ReactNode } from "react";

import type { BlacklistKind } from "@entities/blacklist/api";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";

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
    <Card>
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
    </Card>
  );
}

export function KindBadge({ kind, label }: { kind: BlacklistKind; label: string }) {
  return (
    <Badge tone={kind === "TELEGRAM_ID" ? "accent" : "neutral"} className="w-[84px] justify-center">
      {label}
    </Badge>
  );
}

