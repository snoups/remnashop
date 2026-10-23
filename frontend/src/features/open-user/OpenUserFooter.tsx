import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { OpenUserButton } from "@features/open-user/OpenUserButton";
import { type OpenableUser, isOpenableUser, useCanOpenUsers } from "@features/open-user/openable-user";

export interface OpenUserLink {
  label: string;
  icon: LucideIcon;
  user: OpenableUser | null | undefined;
}

// Equal-width "go to user" buttons pinned under a dialog's body; `children`
// adds the dialog's own actions to the same row.
export function OpenUserFooter({ links, children }: { links: OpenUserLink[]; children?: ReactNode }) {
  const canOpenUsers = useCanOpenUsers();
  const available = canOpenUsers ? links.filter((link) => isOpenableUser(link.user)) : [];
  if (available.length === 0 && !children) return null;

  return (
    <div className="grid shrink-0 auto-cols-fr grid-flow-col gap-2 border-t border-white/[0.08] px-5 py-3.5">
      {available.map((link) => (
        <OpenUserButton key={link.label} {...link} />
      ))}
      {children}
    </div>
  );
}
