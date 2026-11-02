import type { ComponentType } from "react";

import { Switch } from "@shared/ui/glass/Switch";

/** A 36px field-like capsule: icon, label, the switch 4px in (on its curve). The label forwards a
 *  click anywhere on it to the switch. Side by side in a flex row they split it evenly. */
export function ToggleCapsule({
  icon: Icon,
  label,
  checked,
  onChange,
  disabled = false,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="glass-well flex h-9 min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-full pl-3.5 pr-1 has-disabled:cursor-not-allowed">
      <Icon className={`size-4 shrink-0 ${checked ? "text-primary" : "text-muted-foreground"}`} />
      <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">{label}</span>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
    </label>
  );
}
