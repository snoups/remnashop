import { ArrowLeft } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";

/** The inspector's head: what is open and where it lives; a back arrow from the text or a button to its window. */
export function InspectorHeader({
  title,
  subtitle,
  onBack,
}: {
  title: ReactNode;
  subtitle: ReactNode;
  onBack?: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      {onBack && (
        <IconButton size="9" tone="glass" onClick={onBack}>
          <ArrowLeft className="size-4 text-foreground" />
        </IconButton>
      )}
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-base font-semibold tracking-tight text-foreground">{title}</h3>
        <div className="truncate text-xs text-muted-foreground">{subtitle}</div>
      </div>
    </div>
  );
}

/** A line across the inspector card between its groups. */
export function InspectorDivider() {
  return <div className="-mx-4 border-t border-white/[0.08]" />;
}

/** A 36px line, label left and the switch at the end: the height of every other control in the inspector. */
export function SwitchRow({
  label,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex h-9 cursor-pointer items-center justify-between gap-3 has-disabled:cursor-not-allowed">
      <span className="text-sm font-medium text-foreground">{label}</span>
      <Switch checked={checked} disabled={disabled} onChange={onChange} />
    </label>
  );
}

/** One line of explanation under the header: why a window is out of reach. */
export function InspectorNote({
  icon: Icon,
  warning = false,
  text,
}: {
  icon: ComponentType<{ className?: string }>;
  warning?: boolean;
  text: string;
}) {
  return (
    <p className={`flex items-start gap-2 text-xs ${warning ? "text-warning" : "text-muted-foreground"}`}>
      <Icon className="mt-px size-3.5 shrink-0" />
      {text}
    </p>
  );
}
