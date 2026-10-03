import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { deleteAdmin } from "@entities/admin/api";
import { resetUserReferralCode } from "@entities/referrals/api";
import { type UserListItem, blockUser, deleteUser, unblockUser } from "@entities/user/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { PromoteAdminDialog } from "@features/admin-promote/PromoteAdminDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import type { Role } from "@shared/types/rbac";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

export type UserAction = "promote" | "block" | "unblock" | "resetReferralCode" | "delete";

interface UserActionsOptions {
  /** the account after a promote, block, unblock or referral code reset */
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

const ROLE_RANK: Record<Role, number> = { USER: 0, ADMIN: 1, OWNER: 2, SYSTEM: 3 };

/** Account actions with their confirmations, shared by the users list menu and the user card. */
export function useUserActions({ onUpdated, onDeleted }: UserActionsOptions): UserActions {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const currentUserState = useCurrentUser();
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  const currentRole = currentUserState.kind === "ready" ? currentUserState.data.role : "USER";
  const [pending, setPending] = useState<{
    action: "promote" | "blockAdmin" | "resetReferralCode" | "delete";
    user: UserListItem;
  } | null>(null);

  const available = (user: UserListItem): UserAction[] => {
    // a deleted account is read-only
    if (user.deleted_at) return [];
    // the backend's can_manage: a customer is anyone's, staff only from a strictly higher role,
    // which also keeps everyone off their own account
    const canManage = user.role === "USER" || ROLE_RANK[currentRole] > ROLE_RANK[user.role];
    // blocking an admin demotes them, behind the same gate as a demotion
    const canBlock = canManage && (user.role !== "ADMIN" || permissions.includes("ADMINS_MANAGE"));
    const canDelete =
      user.id !== currentUserId &&
      ((user.role === "ADMIN" && permissions.includes("ADMINS_MANAGE")) ||
        (user.role === "USER" && permissions.includes("USERS_DELETE")));
    return [
      ...(user.role === "USER" && permissions.includes("ADMINS_MANAGE") ? ["promote" as const] : []),
      ...(user.is_blocked
        ? canManage && permissions.includes("USERS_UNBLOCK")
          ? ["unblock" as const]
          : []
        : canBlock && permissions.includes("USERS_BLOCK")
          ? ["block" as const]
          : []),
      ...(user.referral_code && permissions.includes("REFERRALS_CODE_RESET") ? ["resetReferralCode" as const] : []),
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

  const resetReferralCode = async (user: UserListItem) => {
    try {
      const stats = await resetUserReferralCode(user.id);
      onUpdated({ ...user, referral_code: stats.referral_code });
      toast.success(t("referrals.stats.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.stats.resetError")));
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
    // blocking an admin also demotes them and drops their sessions, so confirm first
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
        cancelLabel={t("common.cancel")}
        danger
        onConfirm={() => {
          void setBlocked(pending.user, true);
          close();
        }}
        onCancel={close}
      />
    ) : pending.action === "resetReferralCode" ? (
      <ConfirmDialog
        title={t("referrals.stats.resetConfirmTitle")}
        message={t("referrals.stats.resetConfirmText")}
        confirmLabel={t("referrals.stats.resetCode")}
        cancelLabel={t("common.cancel")}
        danger
        onConfirm={() => {
          void resetReferralCode(pending.user);
          close();
        }}
        onCancel={close}
      />
    ) : (
      <ConfirmDialog
        title={t("users.delete.confirmTitle")}
        message={t("users.delete.confirm", { name: pending.user.name })}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
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
