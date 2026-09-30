import { ArrowUpRight, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type UserListItem, listUsers } from "@entities/user/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
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
  const currentUser = useCurrentUser();
  const permissions = currentUser.kind === "ready" ? currentUser.data.effective_permissions : [];
  const [isLoading, setIsLoading] = useState(false);
  const [opened, setOpened] = useState<UserListItem | null>(null);

  const canOpenUsers = useCanOpenUsers();

  if (!isOpenableUser(user) || !canOpenUsers) return null;
  const userId = user.id;

  const handleClick = async () => {
    setIsLoading(true);
    try {
      // search also matches telegram_id, so pick the exact id out of the page
      const page = await listUsers({
        search: String(userId),
        includeStaff: permissions.includes("ADMINS_MANAGE"),
        // history (payments, events) still points at deleted accounts
        deleted: "include",
      });
      const found = page.items.find((item) => item.id === userId);
      if (found) setOpened(found);
      else toast.error(t("users.openUserNotFound"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.loadError")));
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
