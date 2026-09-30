import type { LucideIcon } from "lucide-react";

import { OpenUserButton } from "@features/open-user/OpenUserButton";
import { type OpenableUser, isOpenableUser, useCanOpenUsers } from "@features/open-user/openable-user";

export interface OpenUserLink {
  label: string;
  icon: LucideIcon;
  user: OpenableUser | null | undefined;
}

// Equal-width "go to user" buttons pinned under a dialog's body.
export function OpenUserFooter({ links }: { links: OpenUserLink[] }) {
  const canOpenUsers = useCanOpenUsers();
  const available = links.filter((link) => isOpenableUser(link.user));
  if (!canOpenUsers || available.length === 0) return null;

  return (
    <div className="grid shrink-0 auto-cols-fr grid-flow-col gap-2 border-t border-white/[0.07] px-5 py-3.5">
      {available.map((link) => (
        <OpenUserButton key={link.label} {...link} />
      ))}
    </div>
  );
}
