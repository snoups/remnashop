import { User } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { initials } from "@shared/lib/initials";
import { Row } from "@shared/ui/glass/Row";

interface UserRowProps {
  /** empty for a deleted account: shown as users.deleted.name */
  name: string | null | undefined;
  /** set: a mono #id after the name, as in the users list; pair it with a name that has no id of its own */
  id?: number;
  /** the account has no name of its own: a user icon instead of initials */
  unnamed?: boolean;
  subtitle: ReactNode;
  /** badges, a tag or an amount on the right */
  aside?: ReactNode;
  /** omitted when there is no user row to open */
  onClick?: () => void;
}

/** A user in a DialogCard list: a Row size="sm" with initials, name, subtitle; opens their card on click. */
export function UserRow({ name, id, unnamed = false, subtitle, aside, onClick }: UserRowProps) {
  const { t } = useTranslation();
  return (
    <Row
      size="sm"
      glyph={unnamed ? <User className="size-4" /> : <span className="text-[11px] font-bold">{initials(name)}</span>}
      label={
        <>
          <span className="truncate">{name || t("users.deleted.name")}</span>
          {id !== undefined && <span className="shrink-0 font-mono text-[12px] font-normal text-muted-foreground">#{id}</span>}
        </>
      }
      description={subtitle}
      onClick={onClick}
    >
      {aside}
    </Row>
  );
}
