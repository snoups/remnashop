import type { ComponentType, ReactNode } from "react";

interface CardHeaderProps {
  icon: ComponentType<{ className?: string }>;
  title: ReactNode;
  description: ReactNode;
  /** badges and actions on the right; wraps under the text once that would drop below 14rem */
  aside?: ReactNode;
}

/** Header of a page/settings Card: icon, title, description, then a divider across the card. */
export function CardHeader({ icon: Icon, title, description, aside }: CardHeaderProps) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-3">
        <div className="flex min-w-0 flex-1 basis-56 items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground">
            <Icon className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">{title}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{description}</p>
          </div>
        </div>
        {aside && <div className="flex shrink-0 items-center gap-2">{aside}</div>}
      </div>
      <div className="-mx-4 mt-4 border-t border-white/[0.08]" />
    </>
  );
}
