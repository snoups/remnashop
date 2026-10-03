import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { deleteAdmin } from "@entities/admin/api";
import { type UserListItem, blockUser, deleteUser, unblockUser } from "@entities/user/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { PromoteAdminDialog } from "@features/admin-promote/PromoteAdminDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

export type UserAction = "promote" | "block" | "unblock" | "delete";

interface UserActionsOptions {
  /** the account after a promote, block or unblock */
  onUpdated: (user: UserListItem) => void;
  onDeleted: (user: UserListItem) => void;
}

interface UserActions {
  /** what the viewer may do to this account, in footer order */
  available: (user: UserListItem) => UserAction[];
  run: (action: UserAction, user: UserListItem) => void;
  /** confirmations and the promote form; render it where they should stack */
  dialogs: ReactNode;
}

/** Account actions with their confirmations, shared by the users list menu and the user card. */
export function useUserActions({ onUpdated, onDeleted }: UserActionsOptions): UserActions {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const currentUserState = useCurrentUser();
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  const [pending, setPending] = useState<{ action: "promote" | "blockAdmin" | "delete"; user: UserListItem } | null>(
    null,
  );

  const available = (user: UserListItem): UserAction[] => {
    // a deleted account is read-only
    if (user.deleted_at) return [];
    const canDelete =
      user.id !== currentUserId &&
      ((user.role === "ADMIN" && permissions.includes("ADMINS_MANAGE")) ||
        (user.role === "USER" && permissions.includes("USERS_DELETE")));
    return [
      ...(user.role === "USER" && permissions.includes("ADMINS_MANAGE") ? ["promote" as const] : []),
      ...(permissions.includes(user.is_blocked ? "USERS_UNBLOCK" : "USERS_BLOCK")
        ? [user.is_blocked ? ("unblock" as const) : ("block" as const)]
        : []),
      ...(canDelete ? ["delete" as const] : []),
    ];
  };

  const setBlocked = async (user: UserListItem, blocked: boolean) => {
    try {
      onUpdated(await (blocked ? blockUser(user.id) : unblockUser(user.id)));
    } catch (err) {
      toast.error(getErrorMessage(err, t(blocked ? "users.block.error" : "users.unblock.error")));
    }
  };

  const remove = async (user: UserListItem) => {
    try {
      await (user.role === "ADMIN" ? deleteAdmin(user.id) : deleteUser(user.id));
      onDeleted(user);
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.delete.error")));
    }
  };

  const run = (action: UserAction, user: UserListItem) => {
    if (action === "unblock") void setBlocked(user, false);
    // blocking an admin also demotes them and drops their sessions -- confirm first
    else if (action === "block") {
      if (user.role === "ADMIN") setPending({ action: "blockAdmin", user });
      else void setBlocked(user, true);
    } else setPending({ action, user });
  };

  const close = () => setPending(null);

  const dialogs =
    pending === null ? null : pending.action === "promote" ? (
      <PromoteAdminDialog
        user={pending.user}
        onPromoted={(login) => onUpdated({ ...pending.user, role: "ADMIN", login })}
        onClose={close}
      />
    ) : pending.action === "blockAdmin" ? (
      <ConfirmDialog
        title={t("users.blockAdmin.title")}
        message={t("users.blockAdmin.confirm", { name: pending.user.name })}
        confirmLabel={t("users.blockAdmin.confirmButton")}
        cancelLabel={t("users.blockAdmin.cancelButton")}
        danger
        onConfirm={() => {
          void setBlocked(pending.user, true);
          close();
        }}
        onCancel={close}
      />
    ) : (
      <ConfirmDialog
        title={t("users.delete.confirmTitle")}
        message={t("users.delete.confirm", { name: pending.user.name })}
        confirmLabel={t("users.delete.confirmButton")}
        cancelLabel={t("users.delete.cancelButton")}
        danger
        onConfirm={() => {
          void remove(pending.user);
          close();
        }}
        onCancel={close}
      />
    );

  return { available, run, dialogs };
}
