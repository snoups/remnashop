import type { ComponentType, ReactNode } from "react";

import type { BlacklistKind } from "@entities/blacklist/api";
import { Badge } from "@shared/ui/Badge";
import { Section } from "@shared/ui/glass/Section";

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
    <Section icon={icon} title={title} description={description} aside={action}>
      {children}
    </Section>
  );
}

export function KindBadge({ kind, label }: { kind: BlacklistKind; label: string }) {
  return (
    <Badge tone={kind === "TELEGRAM_ID" ? "accent" : "neutral"} className="w-[84px] justify-center">
      {label}
    </Badge>
  );
}
