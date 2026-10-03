import type { ComponentType, ReactNode } from "react";

import type { BlacklistKind } from "@entities/blacklist/api";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

export function BlacklistCard({
  icon,
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
      <CardHeader icon={icon} title={title} description={description} aside={action} />
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

