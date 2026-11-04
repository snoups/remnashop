import type { HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

import { GLASS_LIST_ROW_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

interface ListRowProps extends Omit<HTMLMotionProps<"button">, "children" | "className"> {
  /** the columns: the table's grid template (ROW_GRID_CLASSNAME...); layout only */
  className?: string;
  /** on a glass page: a 32px circle 14px in, as a settings Row (36px, 12px otherwise) */
  glass?: boolean;
  children?: ReactNode;
}

/** A table row that opens its details. Disabled (no permission to open): no hover, no ripple, default cursor. */
export function ListRow({ className = "", glass = false, children, ...props }: ListRowProps) {
  return (
    <Pressable
      className={`w-full text-left ${glass ? GLASS_LIST_ROW_CLASS : LIST_ROW_CLASS} enabled:hover:bg-white/[0.04] disabled:cursor-default ${className}`}
      {...props}
    >
      {children}
    </Pressable>
  );
}
