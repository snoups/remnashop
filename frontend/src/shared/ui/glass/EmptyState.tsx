import { AlertCircle, Inbox, type LucideIcon } from "lucide-react";

const PADDING = {
  // a list that is the whole page
  page: "py-12",
  // inside a card, dialog or panel
  card: "py-8",
} as const;

interface EmptyStateProps {
  text: string;
  icon?: LucideIcon;
  size?: keyof typeof PADDING;
}

/** Nothing to list: a bare 20px icon, 13px muted text under it, medium so its strokes are as heavy as
 *  the icon's (1.67px at 20px). */
export function EmptyState({ text, icon: Icon = Inbox, size = "card" }: EmptyStateProps) {
  return (
    <div className={`flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground ${PADDING[size]}`}>
      <Icon className="size-5" />
      <p className="text-center text-[13px] font-medium">{text}</p>
    </div>
  );
}

/** EmptyState's layout in the error tone, for a block whose data failed to load. */
export function ErrorState({ text, size = "card" }: Omit<EmptyStateProps, "icon">) {
  return (
    <div className={`flex flex-1 flex-col items-center justify-center gap-2 text-error ${PADDING[size]}`}>
      <AlertCircle className="size-5" />
      <p className="text-center text-[13px] font-medium">{text}</p>
    </div>
  );
}
