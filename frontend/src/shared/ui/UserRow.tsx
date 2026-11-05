import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { initials } from "@shared/lib/initials";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Pressable } from "@shared/ui/Pressable";

interface UserRowProps {
  /** empty for a deleted account: shown as users.deleted.name */
  name: string | null | undefined;
  subtitle: ReactNode;
  /** badges, a tag or an amount on the right */
  aside?: ReactNode;
  /** omitted when there is no user row to open */
  onClick?: () => void;
}

/** A user in a Card variant="list": initials, name, subtitle; opens their card on click.
 *  48px pill: the 32px circle 8px in on every side, a 20px badge on the right 14px in, as on its curve. */
export function UserRow({ name, subtitle, aside, onClick }: UserRowProps) {
  const { t } = useTranslation();
  return (
    <Pressable
      type="button"
      disabled={!onClick}
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-full py-2 pl-2 pr-3.5 text-left transition-colors enabled:hover:bg-white/[0.04] disabled:cursor-default"
    >
      <IconCircle glyph={<span className="text-[11px] font-bold">{initials(name)}</span>} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">
          {name || t("users.deleted.name")}
        </p>
        <p className="truncate text-[12px] leading-tight text-muted-foreground">{subtitle}</p>
      </div>
      {aside}
    </Pressable>
  );
}
