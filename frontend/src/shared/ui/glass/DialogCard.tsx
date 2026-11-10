import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { ComponentType, ReactNode } from "react";

import { GLASS_PLATE_CLASS, SECTION_TITLE_CLASS } from "@shared/ui/classes";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { Pressable } from "@shared/ui/Pressable";

const PADDING = {
  list: "p-1.5",
  form: "flex flex-col gap-3 px-3.5 pb-3.5",
} as const;

/** Card's list and form layouts on a glass dialog's 12px corners. */
export function DialogCard({
  variant = "list",
  title,
  icon: Icon,
  collapsible = false,
  children,
}: {
  /** list: InfoRow rows; form: fields and blocks, 14px in */
  variant?: keyof typeof PADDING;
  title?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  /** list with a title: starts folded, the title toggles it */
  collapsible?: boolean;
  children: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  // a form title's pt-2 plus pt-1.5 puts its text where pt-3.5 puts untitled content
  const top = variant === "form" ? (title ? "pt-1.5" : "pt-3.5") : "";
  const heading = title && (
    <>
      {Icon && <Icon className="size-3.5" />}
      {title}
    </>
  );
  return (
    <div className={`${GLASS_PLATE_CLASS} ${PADDING[variant]} ${top}`}>
      {collapsible && title ? (
        <>
          {/* the list title's type at a full row's height, so the folded card is a tappable strip */}
          <Pressable
            type="button"
            onClick={() => setIsOpen((open) => !open)}
            className="flex w-full items-center gap-1.5 rounded-full px-2.5 py-2 text-xs font-semibold uppercase tracking-wide text-foreground transition-colors hover:bg-white/[0.04]"
          >
            {heading}
            <ChevronDown
              className={`ml-auto size-3.5 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
            />
          </Pressable>
          <AnimatedHeight>{isOpen && children}</AnimatedHeight>
        </>
      ) : (
        <>
          {title && (
            <h3
              className={
                variant === "list"
                  ? SECTION_TITLE_CLASS
                  : "flex items-center gap-1.5 pt-2 text-xs font-semibold uppercase tracking-wide text-foreground"
              }
            >
              {heading}
            </h3>
          )}
          {children}
        </>
      )}
    </div>
  );
}
