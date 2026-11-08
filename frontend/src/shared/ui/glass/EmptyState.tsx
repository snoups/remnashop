import { AlertCircle, Inbox, type LucideIcon } from "lucide-react";

export const STATE_PADDING = {
  // a list that is the whole page
  page: "py-12",
  // inside a card, dialog or panel
  card: "py-8",
} as const;

interface EmptyStateProps {
  text: string;
  icon?: LucideIcon;
  size?: keyof typeof STATE_PADDING;
}

function StateMessage({ text, icon: Icon, size, tone }: Required<EmptyStateProps> & { tone: string }) {
  return (
    <div className={`flex flex-1 flex-col items-center justify-center gap-2 ${tone} ${STATE_PADDING[size]}`}>
      <Icon className="size-5" />
      <p className="whitespace-pre-line text-center text-[13px] font-semibold">{text}</p>
    </div>
  );
}

/** Nothing to list: a bare 20px icon, 13px muted text under it, semibold so its strokes are as heavy as
 *  the icon's (1.67px at 20px). */
export function EmptyState({ text, icon = Inbox, size = "card" }: EmptyStateProps) {
  return <StateMessage text={text} icon={icon} size={size} tone="text-muted-foreground" />;
}

/** EmptyState's layout in the error tone, for a block whose data failed to load. */
export function ErrorState({ text, size = "card" }: Omit<EmptyStateProps, "icon">) {
  return <StateMessage text={text} icon={AlertCircle} size={size} tone="text-error" />;
}
