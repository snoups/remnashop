import { motion } from "motion/react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap } from "@shared/lib/bounceState";
import { initials } from "@shared/lib/initials";

interface UserRowProps {
  /** empty for a deleted account: shown as users.deleted.name */
  name: string | null | undefined;
  subtitle: ReactNode;
  /** badges, a tag or an amount on the right */
  aside?: ReactNode;
  /** omitted when there is no user row to open */
  onClick?: () => void;
}

/** A user in a Card variant="list": initials, name, subtitle; opens their card on click. */
export function UserRow({ name, subtitle, aside, onClick }: UserRowProps) {
  const { t } = useTranslation();
  return (
    <motion.button
      type="button"
      disabled={!onClick}
      onClick={onClick}
      {...(onClick && bounceTap(0.03))}
      className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors enabled:hover:bg-white/[0.04] disabled:cursor-default"
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground">
        {initials(name)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">
          {name || t("users.deleted.name")}
        </p>
        <p className="truncate text-[12px] leading-tight text-muted-foreground">{subtitle}</p>
      </div>
      {aside}
    </motion.button>
  );
}
