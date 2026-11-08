import { useTranslation } from "react-i18next";

import { deleteAdmin, demoteAdmin } from "@entities/admin/api";
import type { UserListItem } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface DemoteAdminConfirmProps {
  user: UserListItem;
  /** Telegram, email or OAuth left once the login is cleared; false adds a warning */
  canSignInAfterDemote: boolean;
  onDemoted: (user: UserListItem) => void;
  onClose: () => void;
}

export function DemoteAdminConfirm({ user, canSignInAfterDemote, onDemoted, onClose }: DemoteAdminConfirmProps) {
  const { t } = useTranslation();

  const handleConfirm = async () => {
    onClose();
    try {
      onDemoted(await demoteAdmin(user.id));
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
      onCancel={onClose}
    />
  );
}

interface DeleteAdminConfirmProps {
  user: UserListItem;
  onDeleted: () => void;
  onClose: () => void;
}

export function DeleteAdminConfirm({ user, onDeleted, onClose }: DeleteAdminConfirmProps) {
  const { t } = useTranslation();

  const handleConfirm = async () => {
    onClose();
    try {
      await deleteAdmin(user.id);
      onDeleted();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.delete.error")));
    }
  };

  return (
    <ConfirmDialog
      title={t("admins.delete.title")}
      message={t("admins.delete.confirm", { name: user.name })}
      confirmLabel={t("common.delete")}
      cancelLabel={t("common.cancel")}
      danger
      onConfirm={() => void handleConfirm()}
      onCancel={onClose}
    />
  );
}
