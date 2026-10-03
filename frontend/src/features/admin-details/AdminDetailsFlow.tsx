import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, demoteAdmin } from "@entities/admin/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { AdminDetailsDialog, type AdminDetailsTab } from "@features/admin-details/AdminDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface DemoteAdminConfirmProps {
  admin: Admin;
  onDemoted: () => void;
  onClose: () => void;
  /** defaults to onClose */
  onCancel?: () => void;
}

export function DemoteAdminConfirm({ admin, onDemoted, onClose, onCancel = onClose }: DemoteAdminConfirmProps) {
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
      message={t("admins.demote.confirm")}
      confirmLabel={t("admins.demote.button")}
      cancelLabel={t("common.cancel")}
      danger
      onConfirm={() => void handleConfirm()}
      onCancel={onCancel}
    />
  );
}

interface AdminDetailsFlowProps {
  admin: Admin;
  initialTab?: AdminDetailsTab;
  /** Permissions saved or the admin demoted. */
  onChanged: () => void;
  onClose: () => void;
}

/** The admin details dialog plus its demote follow-up, usable outside the Admins page. */
export function AdminDetailsFlow({ admin, initialTab, onChanged, onClose }: AdminDetailsFlowProps) {
  const currentUser = useCurrentUser();
  const [isDemoting, setIsDemoting] = useState(false);
  const permissions = usePermissions();
  const isSelf = currentUser.kind === "ready" && currentUser.data.id === admin.id;

  // cancelling the confirm goes back to the details dialog, not out of the flow
  if (isDemoting) {
    return (
      <DemoteAdminConfirm
        admin={admin}
        onDemoted={onChanged}
        onClose={onClose}
        onCancel={() => setIsDemoting(false)}
      />
    );
  }

  return (
    <AdminDetailsDialog
      admin={admin}
      initialTab={initialTab}
      canViewSessions={permissions.includes("USER_SESSIONS_VIEW") && !isSelf}
      canViewEvents={permissions.includes("EVENT_LOG_VIEW")}
      onUpdated={onChanged}
      onClose={(followUp) => (followUp === "demote" ? setIsDemoting(true) : onClose())}
    />
  );
}
