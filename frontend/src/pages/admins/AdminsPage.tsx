import { History, KeyRound, LaptopMinimal, ShieldPlus, Trash2, UserMinus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, listAdmins } from "@entities/admin/api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import { prefetchPermissionCatalog } from "@entities/admin/use-permission-catalog";
import { AdminCreateDialog } from "@features/admin-create/AdminCreateDialog";
import { DeleteAdminConfirm, DemoteAdminConfirm } from "@features/admin-details/AdminConfirms";
import { UserDetailsDialog, type UserDetailsTab } from "@features/user-details/UserDetailsDialog";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { initials } from "@shared/lib/initials";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { PAGE_CLASS, PAGE_SCROLL_CLASS } from "@shared/ui/classes";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { SectionRows } from "@shared/ui/glass/Section";
import { OneTimeSecretDialog } from "@shared/ui/OneTimeSecretDialog";
import { Pressable } from "@shared/ui/Pressable";
import { Spinner } from "@shared/ui/Spinner";

// the create row turns primary on hover, its icon too
function CreateAdminIcon({ className = "" }: { className?: string }) {
  return <ShieldPlus className={`${className} transition-colors group-hover:text-primary`} />;
}

export function AdminsPage() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listAdmins);
  const [isCreating, setIsCreating] = useState(false);
  const [revealedPassword, setRevealedPassword] = useState<string | null>(null);
  const [details, setDetails] = useState<{ admin: Admin; tab: UserDetailsTab } | null>(null);
  const [pendingDemote, setPendingDemote] = useState<Admin | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Admin | null>(null);
  const currentUserState = useCurrentUser();

  // warm the catalog so the details dialog's Permissions tab opens without a spinner
  useEffect(prefetchPermissionCatalog, []);
  const permissions = usePermissions();
  const canViewSessions = permissions.includes("USER_SESSIONS_VIEW");
  const canViewEvents = permissions.includes("EVENT_LOG_VIEW");
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  const canSignInAfterDemote = (admin: Admin) =>
    state.kind === "ready" && state.data.customer_sign_in_ids.includes(admin.id);

  const menuItemsFor = (admin: Admin): ActionMenuItem[] => {
    const items: ActionMenuItem[] = [];
    if (admin.role === "ADMIN") {
      items.push({
        label: t("admins.details.tabs.permissions"),
        icon: KeyRound,
        onClick: () => setDetails({ admin, tab: "permissions" }),
      });
    }
    if (canViewSessions) {
      items.push({
        label: t("admins.details.tabs.sessions"),
        icon: LaptopMinimal,
        onClick: () => setDetails({ admin, tab: "sessions" }),
      });
    }
    if (canViewEvents) {
      items.push({
        label: t("admins.details.tabs.events"),
        icon: History,
        onClick: () => setDetails({ admin, tab: "events" }),
      });
    }
    if (admin.role === "ADMIN") {
      items.push({
        label: t("admins.demote.button"),
        icon: UserMinus,
        variant: "danger",
        separatorBefore: true,
        onClick: () => setPendingDemote(admin),
      });
      // demoting would leave no way in, so the account may as well go
      if (!canSignInAfterDemote(admin)) {
        items.push({
          label: t("common.delete"),
          icon: Trash2,
          variant: "danger",
          onClick: () => setPendingDelete(admin),
        });
      }
    }
    return items;
  };

  return (
    // its own scroller: main's fade would dim the card at rest. data-under-header: the header's 20px
    // padding moves into this one, where the fade (scroll-fade-gap) sits
    <div data-fills-main data-under-header className={PAGE_CLASS}>
      <div
        className={PAGE_SCROLL_CLASS}
      >
        <LoadGate>
        <LoadGateHold isLoading={state.kind === "loading"} />
        <div className="glass-panel rounded-3xl p-4">
          <AnimatedHeight>
          {state.kind === "loading" && <Spinner size="card" />}
          {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
          {state.kind === "ready" && (
            <>
              {/* a Row's geometry: 60px pill, 32px circle 14px in */}
              <Pressable
                type="button"
                onClick={() => setIsCreating(true)}
                className="group mb-2 flex min-h-15 w-full items-center gap-3 rounded-full border border-dashed border-glass-border px-3.5 text-[13px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-primary"
              >
                <IconCircle icon={CreateAdminIcon} />
                {t("admins.create.button")}
              </Pressable>
              <SectionRows flush>
                {[...state.data.items].sort((a, b) => Number(b.id === currentUserId) - Number(a.id === currentUserId)).map((admin) => (
                  <Row
                    key={admin.id}
                    glyph={
                      <span className={`text-[11px] font-bold ${admin.id === currentUserId ? "text-primary" : ""}`}>
                        {initials(admin.login ?? admin.name)}
                      </span>
                    }
                    label={admin.name}
                    description={<span className="font-mono">{admin.login ?? "—"}</span>}
                    onClick={() => setDetails({ admin, tab: "profile" })}
                  >
                    {/* the row's end item when there's no menu: 20px in, as far from the side as from top and bottom */}
                    <Badge tone={ROLE_BADGE_TONE[admin.role]} className={admin.id === currentUserId ? "mr-1.5" : ""}>
                      {t(`roles.${admin.role}`)}
                    </Badge>
                    {admin.id !== currentUserId && <ActionMenu items={menuItemsFor(admin)} />}
                  </Row>
                ))}
              </SectionRows>
            </>
          )}
          </AnimatedHeight>

          {isCreating && (
            <AdminCreateDialog
              onClose={() => setIsCreating(false)}
              onCreated={(password) => {
                setRevealedPassword(password);
                reload();
              }}
            />
          )}

          {details && (
            <UserDetailsDialog
              user={details.admin}
              initialTab={details.tab}
              onChanged={reload}
              onDeleted={reload}
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
            <DemoteAdminConfirm
              user={pendingDemote}
              canSignInAfterDemote={canSignInAfterDemote(pendingDemote)}
              onDemoted={reload} onClose={() => setPendingDemote(null)} />
          )}

          {pendingDelete && (
            <DeleteAdminConfirm user={pendingDelete} onDeleted={reload} onClose={() => setPendingDelete(null)} />
          )}
        </div>
        </LoadGate>
      </div>
    </div>
  );
}
