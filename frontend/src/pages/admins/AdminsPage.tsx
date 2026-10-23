import { History, KeyRound, LaptopMinimal, UserMinus } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, listAdmins } from "@entities/admin/api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import { prefetchPermissionCatalog } from "@entities/admin/use-permission-catalog";
import { AdminCreateForm } from "@features/admin-create/AdminCreateForm";
import type { AdminDetailsTab } from "@features/admin-details/AdminDetailsDialog";
import { AdminDetailsFlow, DemoteAdminConfirm } from "@features/admin-details/AdminDetailsFlow";
import { bounceTap } from "@shared/lib/bounceState";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { initials } from "@shared/lib/initials";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { LIST_DIVIDER_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { OneTimeSecretDialog } from "@shared/ui/OneTimeSecretDialog";

export function AdminsPage() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listAdmins);
  const [revealedPassword, setRevealedPassword] = useState<string | null>(null);
  const [details, setDetails] = useState<{ admin: Admin; tab: AdminDetailsTab } | null>(null);
  const [pendingDemote, setPendingDemote] = useState<Admin | null>(null);
  const currentUserState = useCurrentUser();

  // warm the catalog so the details dialog's Permissions tab opens without a spinner
  useEffect(prefetchPermissionCatalog, []);
  const permissions = usePermissions();
  const canViewSessions = permissions.includes("USER_SESSIONS_VIEW");
  const canViewEvents = permissions.includes("EVENT_LOG_VIEW");
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;

  return (
    <Card>
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <ErrorState text={t("common.loadError")} size="page" />
      )}
      {state.kind === "ready" && (
        <>
          <AdminCreateForm
            onCreated={(password) => {
              setRevealedPassword(password);
              reload();
            }}
          />

          <div className={`grid grid-cols-[auto_minmax(0,max-content)_auto_1fr_auto] gap-x-3 ${LIST_DIVIDER_CLASS}`}>
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
                  label: t("admins.details.tabs.sessions"),
                  icon: LaptopMinimal,
                  onClick: () => setDetails({ admin, tab: "sessions" }),
                });
              }
              if (canViewEvents) {
                menuItems.push({
                  label: t("admins.details.tabs.events"),
                  icon: History,
                  onClick: () => setDetails({ admin, tab: "events" }),
                });
              }
              if (admin.role === "ADMIN") {
                menuItems.push({
                  label: t("admins.demote.button"),
                  icon: UserMinus,
                  variant: "danger",
                  separatorBefore: true,
                  onClick: () => setPendingDemote(admin),
                });
              }

              return (
                <motion.div
                  key={admin.id}
                  {...bounceTap(0.03)}
                  className={`relative col-span-full grid grid-cols-subgrid items-center has-[[aria-expanded=true]]:z-20 gap-y-0 ${LIST_ROW_CLASS} hover:bg-white/[0.04]`}
                >
                  {/* whole-row hit area; sits under the menu and channel icons (z-10) */}
                  <button
                    type="button"
                    onClick={() => setDetails({ admin, tab: "profile" })}
                    className="absolute inset-0 cursor-pointer rounded-full"
                  />
                  <div
                    className={`row-span-2 flex size-9 items-center justify-center rounded-full text-[12.5px] font-bold ${
                      admin.id === currentUserId ? "bg-accent text-primary" : "bg-white/[0.06] text-foreground"
                    }`}
                  >
                    {initials(admin.login ?? admin.name)}
                  </div>
                  <p className="min-w-0 truncate text-[13px] font-medium text-foreground">{admin.name}</p>
                  <div className="flex items-center gap-2">
                    <Badge tone={ROLE_BADGE_TONE[admin.role]}>
                      {t(`roles.${admin.role}`)}
                    </Badge>
                  </div>
                  <div className="relative z-10 col-start-5 row-span-2 row-start-1 flex items-center justify-end">
                    {admin.id !== currentUserId && <ActionMenu items={menuItems} />}
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
        <AdminDetailsFlow
          admin={details.admin}
          initialTab={details.tab}
          onChanged={reload}
          onClose={() => setDetails(null)}
        />
      )}

      {revealedPassword && (
        <OneTimeSecretDialog
          title={t("admins.passwordModal.title")}
          value={revealedPassword}
          onDone={() => setRevealedPassword(null)}
        />
      )}

      {pendingDemote && (
        <DemoteAdminConfirm admin={pendingDemote} onDemoted={reload} onClose={() => setPendingDemote(null)} />
      )}
    </Card>
  );
}

