import { ArrowUpRight, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type UserListItem, getUser } from "@entities/user/api";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { type OpenableUser, isOpenableUser, useCanOpenUsers } from "@features/open-user/openable-user";

interface OpenUserButtonProps {
  label: string;
  icon: LucideIcon;
  user: OpenableUser | null | undefined;
  size?: "sm" | "md";
}

/** Opens the user's card on top of the current dialog; renders nothing when the viewer can't list users. */
export function OpenUserButton({ label, icon: Icon, user, size = "md" }: OpenUserButtonProps) {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [opened, setOpened] = useState<UserListItem | null>(null);

  const canOpenUsers = useCanOpenUsers();

  if (!isOpenableUser(user) || !canOpenUsers) return null;
  const userId = user.id;

  const handleClick = async () => {
    setIsLoading(true);
    try {
      setOpened(await getUser(userId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) toast.error(t("users.openUserNotFound"));
      else toast.error(getErrorMessage(err, t("users.loadError")));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Button variant="outline" size={size} type="button" onClick={() => void handleClick()} disabled={isLoading}>
        {isLoading ? <Loader2 className="size-3.5 animate-spin" /> : <Icon className="size-3.5" />}
        <span className="truncate">{label}</span>
        <ArrowUpRight className="size-3.5" />
      </Button>
      {opened && <UserDetailsDialog user={opened} onClose={() => setOpened(null)} />}
    </>
  );
}
