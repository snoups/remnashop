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

export function EmptyState({ text, icon: Icon = Inbox, size = "card" }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center gap-2 text-muted-foreground ${PADDING[size]}`}>
      <Icon className="size-5" />
      <p className="text-sm">{text}</p>
    </div>
  );
}

/** EmptyState's layout in the error tone, for a block whose data failed to load. */
export function ErrorState({ text, size = "card" }: Omit<EmptyStateProps, "icon">) {
  return (
    <div className={`flex flex-col items-center gap-2 text-error ${PADDING[size]}`}>
      <AlertCircle className="size-5" />
      <p className="text-sm">{text}</p>
    </div>
  );
}
