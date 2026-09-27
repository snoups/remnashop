import { AlertCircle, KeyRound, LaptopMinimal, UserMinus } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, demoteAdmin, listAdmins } from "@entities/admin/api";
import { ROLE_BADGE_CLASSNAME, getAdminInitials } from "@entities/admin/display";
import { prefetchPermissionCatalog } from "@entities/admin/use-permission-catalog";
import { AdminCreateForm } from "@features/admin-create/AdminCreateForm";
import { AdminPasswordModal } from "@features/admin-create/AdminPasswordModal";
import { AdminDetailsDialog, type AdminDetailsTab } from "@features/admin-details/AdminDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useCurrentUser } from "@entities/user/use-current-user";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";

export function AdminsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(listAdmins);
  const [revealedPassword, setRevealedPassword] = useState<string | null>(null);
  const [details, setDetails] = useState<{ admin: Admin; tab: AdminDetailsTab } | null>(null);
  const [pendingDemote, setPendingDemote] = useState<Admin | null>(null);
  const currentUserState = useCurrentUser();

  // warm the catalog so the details dialog's Permissions tab opens without a spinner
  useEffect(prefetchPermissionCatalog, []);
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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      {state.kind === "loading" && <Spinner className="py-12" />}
      {state.kind === "error" && (
        <div className="flex flex-col items-center gap-2 py-12 text-error">
          <AlertCircle className="size-5" />
          <p className="text-sm">{t("admins.loadError")}</p>
        </div>
      )}
      {state.kind === "ready" && (
        <>
          <AdminCreateForm
            onCreated={(password) => {
              setRevealedPassword(password);
              reload();
            }}
          />

          <div className="grid grid-cols-[auto_minmax(0,max-content)_auto_1fr_auto] gap-x-3 divide-y divide-border/50">
            {[...state.data].sort((a, b) => Number(b.id === currentUserId) - Number(a.id === currentUserId)).map((admin) => {
              const menuItems: ActionMenuItem[] = [];
              if (admin.role === "ADMIN") {
                menuItems.push({
                  label: t("admins.details.tabs.permissions"),
                  icon: KeyRound,
                  onClick: () => setDetails({ admin, tab: "permissions" }),
                });
              }
              if (canViewSessions && admin.id !== currentUserId) {
                menuItems.push({
                  label: t("sessions.title"),
                  icon: LaptopMinimal,
                  onClick: () => setDetails({ admin, tab: "sessions" }),
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
                <motion.div
                  key={admin.id}
                  {...bounceTap(bounceStrength, 0.03)}
                  className="relative col-span-full grid grid-cols-subgrid items-center has-[[aria-expanded=true]]:z-20 gap-y-0 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                >
                  {/* whole-row hit area; sits under the menu and channel icons (z-10) */}
                  <button
                    type="button"
                    onClick={() => setDetails({ admin, tab: "profile" })}
                    aria-label={`${t("users.details.button")}: ${admin.name}`}
                    className="absolute inset-0 cursor-pointer rounded-full"
                  />
                  <div
                    className={`row-span-2 flex size-9 items-center justify-center rounded-full text-[12.5px] font-bold ${
                      admin.role === "OWNER" ? "bg-accent text-primary" : "bg-white/[0.06] text-foreground"
                    }`}
                  >
                    {getAdminInitials(admin)}
                  </div>
                  <p className="min-w-0 truncate text-[13.5px] font-medium text-foreground">{admin.name}</p>
                  <div className="flex items-center gap-2">
                    <span
                      className={`shrink-0 rounded-full border px-2 py-px text-[10.5px] font-semibold uppercase tracking-wide ${ROLE_BADGE_CLASSNAME[admin.role]}`}
                    >
                      {t(`roles.${admin.role}`)}
                    </span>
                    {admin.id === currentUserId && (
                      <span className="shrink-0 whitespace-nowrap text-[12px] text-muted-foreground">
                        · {t("admins.you")}
                      </span>
                    )}
                  </div>
                  <div className="relative z-10 col-start-5 row-span-2 row-start-1 flex items-center justify-end">
                    <ActionMenu items={menuItems} />
                  </div>
                  <p className="col-span-3 col-start-2 min-w-0 truncate font-mono text-[12px] text-muted-foreground">
                    {admin.login ?? "—"}
                  </p>
                </motion.div>
              );
            })}
          </div>
        </>
      )}

      {details && (
        <AdminDetailsDialog
          admin={details.admin}
          initialTab={details.tab}
          canViewSessions={canViewSessions && details.admin.id !== currentUserId}
          onUpdated={reload}
          onClose={(followUp) => {
            if (followUp === "demote") setPendingDemote(details.admin);
            setDetails(null);
          }}
        />
      )}

      {revealedPassword && (
        <AdminPasswordModal password={revealedPassword} onClose={() => setRevealedPassword(null)} />
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

