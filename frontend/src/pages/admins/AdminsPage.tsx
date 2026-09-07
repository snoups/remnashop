import { AlertCircle, Info, KeyRound, LaptopMinimal, UserMinus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, demoteAdmin, listAdmins } from "@entities/admin/api";
import { AdminCreateForm } from "@features/admin-create/AdminCreateForm";
import { AdminPasswordModal } from "@features/admin-create/AdminPasswordModal";
import { AdminPermissionsForm } from "@features/admin-update-permissions/AdminPermissionsForm";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import { UserSessionsDialog } from "@features/user-sessions/UserSessionsDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useCurrentUser } from "@entities/user/use-current-user";
import type { Role } from "@shared/types/rbac";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";

const ROLE_BADGE_CLASSNAME: Record<Role, string> = {
  USER: "border-border bg-white/[0.04] text-muted-foreground",
  ADMIN: "border-border bg-white/[0.06] text-foreground/80",
  OWNER: "border-primary/40 bg-accent text-primary",
  SYSTEM: "border-warning/30 bg-warning/10 text-warning",
};

function getInitials(admin: Admin): string {
  return (admin.login ?? admin.name).slice(0, 2).toUpperCase();
}

export function AdminsPage() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listAdmins);
  const [revealedPassword, setRevealedPassword] = useState<string | null>(null);
  const [detailsAdmin, setDetailsAdmin] = useState<Admin | null>(null);
  const [editingAdmin, setEditingAdmin] = useState<Admin | null>(null);
  const [sessionsAdmin, setSessionsAdmin] = useState<Admin | null>(null);
  const [pendingDemote, setPendingDemote] = useState<Admin | null>(null);
  const currentUserState = useCurrentUser();
  const canViewSessions =
    currentUserState.kind === "ready" &&
    currentUserState.data.effective_permissions.includes("USER_SESSIONS_VIEW");
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;

  const handleDemote = async (userId: number) => {
    try {
      await demoteAdmin(userId);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.demote.error")));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex">
        <AdminCreateForm
          onCreated={(password) => {
            setRevealedPassword(password);
            reload();
          }}
        />
      </div>

      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("admins.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <div className="flex flex-col divide-y divide-border/50">
            {state.data.map((admin) => {
              const menuItems: ActionMenuItem[] = [
                {
                  label: t("users.details.button"),
                  icon: Info,
                  onClick: () => setDetailsAdmin(admin),
                },
              ];
              if (canViewSessions) {
                menuItems.push({
                  label: t("sessions.title"),
                  icon: LaptopMinimal,
                  onClick: () => setSessionsAdmin(admin),
                });
              }
              if (admin.role === "ADMIN" || admin.id === currentUserId) {
                menuItems.push({
                  label: t("admins.permissionsForm.title"),
                  icon: KeyRound,
                  onClick: () => setEditingAdmin(admin),
                });
              }
              if (admin.role === "ADMIN") {
                menuItems.push({
                  label: t("admins.demote.button"),
                  icon: UserMinus,
                  variant: "danger",
                  onClick: () => setPendingDemote(admin),
                });
              }

              return (
                <div
                  key={admin.id}
                  className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12.5px] font-bold text-foreground">
                      {getInitials(admin)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-[13.5px] font-medium text-foreground">{admin.name}</p>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${ROLE_BADGE_CLASSNAME[admin.role]}`}
                        >
                          {t(`roles.${admin.role}`)}
                        </span>
                      </div>
                      <p className="truncate font-mono text-[12px] text-muted-foreground">
                        {admin.login ?? "—"}
                      </p>
                    </div>
                  </div>

                  <ActionMenu items={menuItems} />
                </div>
              );
            })}
          </div>
        )}
      </div>

      {detailsAdmin && (
        <UserDetailsDialog user={detailsAdmin} onClose={() => setDetailsAdmin(null)} />
      )}

      {editingAdmin && (
        <AdminPermissionsForm
          admin={editingAdmin}
          readOnly={editingAdmin.id === currentUserId}
          onUpdated={() => {
            setEditingAdmin(null);
            reload();
          }}
          onCancel={() => setEditingAdmin(null)}
        />
      )}

      {revealedPassword && (
        <AdminPasswordModal password={revealedPassword} onClose={() => setRevealedPassword(null)} />
      )}

      {sessionsAdmin && (
        <UserSessionsDialog
          userId={sessionsAdmin.id}
          userName={sessionsAdmin.name}
          onClose={() => setSessionsAdmin(null)}
        />
      )}

      {pendingDemote && (
        <ConfirmDialog
          title={t("admins.demote.title")}
          message={t("admins.demote.confirm")}
          confirmLabel={t("admins.demote.button")}
          cancelLabel={t("admins.demote.cancel")}
          danger
          onConfirm={() => {
            void handleDemote(pendingDemote.id);
            setPendingDemote(null);
          }}
          onCancel={() => setPendingDemote(null)}
        />
      )}
    </div>
  );
}
