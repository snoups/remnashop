import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, deleteAdmin, demoteAdmin } from "@entities/admin/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import {
  AdminDetailsDialog,
  type AdminDetailsFollowUp,
  type AdminDetailsTab,
} from "@features/admin-details/AdminDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface DemoteAdminConfirmProps {
  admin: Admin;
  /** Telegram, email or OAuth left once the login is cleared; false adds a warning */
  canSignInAfterDemote: boolean;
  onDemoted: () => void;
  onClose: () => void;
  /** defaults to onClose */
  onCancel?: () => void;
}

export function DemoteAdminConfirm({ admin, canSignInAfterDemote, onDemoted, onClose, onCancel = onClose }: DemoteAdminConfirmProps) {
  const { t } = useTranslation();

  const handleConfirm = async () => {
    onClose();
    try {
      await demoteAdmin(admin.id);
      onDemoted();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.demote.error")));
    }
  };

  return (
    <ConfirmDialog
      title={t("admins.demote.title")}
      message={
        !canSignInAfterDemote
          ? `${t("admins.demote.confirm")} ${t("admins.demote.noSignIn")}`
          : t("admins.demote.confirm")
      }
      confirmLabel={t("admins.demote.button")}
      cancelLabel={t("common.cancel")}
      danger
      onConfirm={() => void handleConfirm()}
      onCancel={onCancel}
    />
  );
}

interface DeleteAdminConfirmProps {
  admin: Admin;
  onDeleted: () => void;
  onClose: () => void;
  /** defaults to onClose */
  onCancel?: () => void;
}

export function DeleteAdminConfirm({ admin, onDeleted, onClose, onCancel = onClose }: DeleteAdminConfirmProps) {
  const { t } = useTranslation();

  const handleConfirm = async () => {
    onClose();
    try {
      await deleteAdmin(admin.id);
      onDeleted();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.delete.error")));
    }
  };

  return (
    <ConfirmDialog
      title={t("admins.delete.title")}
      message={t("admins.delete.confirm", { name: admin.name })}
      confirmLabel={t("common.delete")}
      cancelLabel={t("common.cancel")}
      danger
      onConfirm={() => void handleConfirm()}
      onCancel={onCancel}
    />
  );
}

interface AdminDetailsFlowProps {
  admin: Admin;
  canSignInAfterDemote: boolean;
  initialTab?: AdminDetailsTab;
  /** Permissions saved, the admin demoted or deleted. */
  onChanged: () => void;
  onClose: () => void;
}

/** The admin details dialog plus its demote and delete follow-ups, usable outside the Admins page. */
export function AdminDetailsFlow({ admin, canSignInAfterDemote, initialTab, onChanged, onClose }: AdminDetailsFlowProps) {
  const currentUser = useCurrentUser();
  const [followUp, setFollowUp] = useState<AdminDetailsFollowUp | null>(null);
  const permissions = usePermissions();
  const isSelf = currentUser.kind === "ready" && currentUser.data.id === admin.id;

  // cancelling the confirm goes back to the details dialog, not out of the flow
  if (followUp === "demote") {
    return (
      <DemoteAdminConfirm
        admin={admin}
        canSignInAfterDemote={canSignInAfterDemote}
        onDemoted={onChanged}
        onClose={onClose}
        onCancel={() => setFollowUp(null)}
      />
    );
  }
  if (followUp === "delete") {
    return <DeleteAdminConfirm admin={admin} onDeleted={onChanged} onClose={onClose} onCancel={() => setFollowUp(null)} />;
  }

  return (
    <AdminDetailsDialog
      admin={admin}
      initialTab={initialTab}
      canViewSessions={permissions.includes("USER_SESSIONS_VIEW") && !isSelf}
      canViewEvents={permissions.includes("EVENT_LOG_VIEW")}
      // demoting would leave no way in, so the account may as well go
      canDelete={!canSignInAfterDemote}
      onUpdated={onChanged}
      onClose={(picked) => (picked ? setFollowUp(picked) : onClose())}
    />
  );
}
