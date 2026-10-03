import { ArrowUpRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { type OpenableUser, isOpenableUser, useCanOpenUsers } from "@features/open-user/openable-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { Button } from "@shared/ui/Button";

interface OpenUserButtonProps {
  label: string;
  icon: LucideIcon;
  user: OpenableUser | null | undefined;
  size?: "sm" | "md";
}

/** Opens the user's card on top of the current dialog; renders nothing when the viewer can't list users. */
export function OpenUserButton({ label, icon: Icon, user, size = "md" }: OpenUserButtonProps) {
  const { openUser } = useOpenEntity();
  const canOpenUsers = useCanOpenUsers();

  if (!isOpenableUser(user) || !canOpenUsers) return null;

  return (
    <Button variant="outline" size={size} type="button" onClick={() => openUser(user.id)}>
      <Icon className="size-3.5" />
      <span className="truncate">{label}</span>
      <ArrowUpRight className="size-3.5" />
    </Button>
  );
}
