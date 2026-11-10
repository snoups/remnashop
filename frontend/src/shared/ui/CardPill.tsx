import type { ComponentType } from "react";

/** A limit on a subscription-style card: icon, optional label, value in bold. */
export function CardPill({
  icon: Icon,
  label,
  value,
  valueClassName = "",
}: {
  icon?: ComponentType<{ className?: string }>;
  label?: string;
  value: string;
  /** a tone for the value */
  valueClassName?: string;
}) {
  return (
    <span className="flex min-w-0 flex-1 items-center justify-between gap-1.5 rounded-full bg-black/[0.22] px-3 py-1.5 text-xs">
      {Icon && <Icon className="size-3.5 shrink-0 text-muted-foreground" />}
      {label && <span className="min-w-0 truncate text-muted-foreground">{label}</span>}
      <span className={`ml-auto shrink-0 font-bold ${valueClassName}`}>{value}</span>
    </span>
  );
}
