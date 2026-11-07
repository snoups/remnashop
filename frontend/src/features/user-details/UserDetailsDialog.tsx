import {
  BarChart3,
  Gift,
  GitMerge,
  History,
  Layers,
  ListX,
  Lock,
  MailCheck,
  MonitorSmartphone,
  Receipt,
  RotateCcw,
  Send,
  Settings2,
  ShieldPlus,
  Ticket,
  Trash2,
  Unlink,
  Unlock,
  User,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ROLE_BADGE_TONE } from "@entities/admin/display";
import type { UserListItem } from "@entities/user/api";
import { userContacts, userName } from "@entities/user/display";
import { useAccountPermissions, useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { GrantSubscriptionDialog } from "@features/subscription-grant/GrantSubscriptionDialog";
import {
  AnalyticsTab,
  InvitedTab,
  PromocodesTab,
  SubscriptionsTab,
  TransactionsTab,
} from "@features/user-details/UserActivityTabs";
import { EventsTab, ProfileTab, SessionsTab } from "@features/user-details/UserDetailsTabs";
import { useUserActions } from "@features/user-details/use-user-actions";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { initials } from "@shared/lib/initials";
import type { Permission } from "@shared/types/rbac";
import { ActionMenu } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

export type UserDetailsTab =
  | "profile"
  | "analytics"
  | "subscriptions"
  | "transactions"
  | "promocodes"
  | "invited"
  | "sessions"
  | "events";

interface UserDetailsDialogProps {
  user: UserListItem;
  initialTab?: UserDetailsTab;
  /** the account after an action from the footer */
  onChanged?: (user: UserListItem) => void;
  /** the account was deleted from the footer; the dialog closes itself */
  onDeleted?: (user: UserListItem) => void;
  onClose: () => void;
}

export function UserDetailsDialog({ onClose, ...props }: UserDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <UserDetailsDialogBody {...props} />
    </Modal>
  );
}

function UserDetailsDialogBody({
  user: initialUser,
  initialTab = "profile",
  onChanged,
  onDeleted,
}: Omit<UserDetailsDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [user, setUser] = useState(initialUser);
  // remounts the subscriptions tab once they're deleted
  const [subscriptionsVersion, setSubscriptionsVersion] = useState(0);
  const handleUpdated = (updated: UserListItem) => {
    setUser(updated);
    onChanged?.(updated);
  };
  const actions = useUserActions({
    onUpdated: handleUpdated,
    onDeleted: (deleted) => {
      onDeleted?.(deleted);
      // a merge deletes the other account while this one stays open
      if (deleted.id === user.id) close();
    },
    onSubscriptionsDeleted: () => setSubscriptionsVersion((version) => version + 1),
  });
  const available = actions.available(user);
  const [tab, setTab] = useState<UserDetailsTab>(initialTab);
  const [contentRef, contentHeight] = useMeasuredHeight();
  const currentUserState = useCurrentUser();
  const permissions = usePermissions();
  // the per-user session endpoints reject yourself
  const isSelf = currentUserState.kind === "ready" && currentUserState.data.id === user.id;
  const isDeleted = Boolean(user.deleted_at);
  const contacts = userContacts(user, t);
  const accountPermissions = useAccountPermissions(user.id);
  const canGrant =
    !isDeleted && accountPermissions.includes("SUBSCRIPTIONS_GRANT") && accountPermissions.includes("PLANS_VIEW");
  const [isGranting, setIsGranting] = useState(false);

  const hasAny = (...required: Permission[]) => required.some((permission) => permissions.includes(permission));
  const tabs: DialogTabItem<UserDetailsTab>[] = [
    { key: "profile", label: t("admins.details.tabs.profile"), icon: User },
    ...(hasAny("TRANSACTIONS_VIEW", "TRANSACTIONS_SUMMARY_VIEW", "REFERRALS_VIEW")
      ? [{ key: "analytics" as const, label: t("users.details.tabs.analytics"), icon: BarChart3 }]
      : []),
    ...(hasAny("SUBSCRIPTIONS_VIEW")
      ? [{ key: "subscriptions" as const, label: t("users.details.tabs.subscriptions"), icon: Layers }]
      : []),
    ...(hasAny("TRANSACTIONS_VIEW")
      ? [{ key: "transactions" as const, label: t("users.details.tabs.transactions"), icon: Receipt }]
      : []),
    ...(hasAny("PROMOCODES_ACTIVATIONS_VIEW")
      ? [{ key: "promocodes" as const, label: t("users.details.tabs.promocodes"), icon: Ticket }]
      : []),
    ...(hasAny("REFERRALS_INVITED_VIEW")
      ? [{ key: "invited" as const, label: t("users.details.tabs.invited"), icon: Users }]
      : []),
    ...(permissions.includes("USER_SESSIONS_VIEW") && !isSelf && !isDeleted
      ? [{ key: "sessions" as const, label: t("admins.details.tabs.sessions"), icon: MonitorSmartphone }]
      : []),
    ...(permissions.includes("EVENT_LOG_VIEW")
      ? [{ key: "events" as const, label: t("admins.details.tabs.events"), icon: History }]
      : []),
  ];

  return (
    <>
      <DialogHeader
        glyph={
          isDeleted ? (
            <Trash2 className="size-4" />
          ) : user.login || user.name ? (
            <span className="text-[11px] font-bold">{initials(user.login ?? user.name)}</span>
          ) : (
            <User className="size-4" />
          )
        }
        danger={user.is_blocked && !isDeleted}
        title={`${userName(user, t)} #${user.id}`}
        subtitle={contacts || undefined}
        actions={
          <>
            {user.role !== "USER" && <Badge borderless tone={ROLE_BADGE_TONE[user.role]}>{t(`roles.${user.role}`)}</Badge>}
            {isDeleted && <Badge borderless tone="neutral">{t("users.deleted.badge")}</Badge>}
            {user.is_blocked && !isDeleted && <Badge borderless tone="error">{t("users.status.blocked")}</Badge>}
          </>
        }
      />

      {tabs.length > 1 && (
        <div className="px-3 pt-3">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={GLASS_DIALOG_BODY_CLASS}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "profile" && <ProfileTab user={user} onChanged={handleUpdated} />}
            {tab === "analytics" && <AnalyticsTab userId={user.id} />}
            {tab === "subscriptions" && <SubscriptionsTab key={subscriptionsVersion} userId={user.id} />}
            {tab === "transactions" && <TransactionsTab userId={user.id} />}
            {tab === "promocodes" && <PromocodesTab userId={user.id} />}
            {tab === "invited" && <InvitedTab userId={user.id} />}
            {tab === "sessions" && <SessionsTab userId={user.id} />}
            {tab === "events" && <EventsTab userId={user.id} by="target" />}
          </div>
        </motion.div>
      </div>

      {(available.length > 0 || canGrant) && (
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} items-center`}>
          <div className="ml-auto">
            <ActionMenu
              glass
              trigger={{ label: t("users.details.actions"), icon: Settings2 }}
              items={[
                ...(canGrant
                  ? [{ label: t("subscriptions.grant.open"), icon: Gift, onClick: () => setIsGranting(true) }]
                  : []),
                ...(available.includes("toggleTrial")
                  ? [
                      {
                        label: t(user.is_trial_available ? "users.trial.revoke" : "users.trial.allow"),
                        icon: Gift,
                        onClick: () => actions.run("toggleTrial", user),
                      },
                    ]
                  : []),
                ...(available.includes("promote")
                  ? [{ label: t("admins.promote.button"), icon: ShieldPlus, onClick: () => actions.run("promote", user) }]
                  : []),
                ...(available.includes("bindTelegram")
                  ? [{ label: t("users.telegram.action"), icon: Send, onClick: () => actions.run("bindTelegram", user) }]
                  : []),
                ...(available.includes("unbindTelegram")
                  ? [{ label: t("users.telegram.unbind"), icon: Unlink, onClick: () => actions.run("unbindTelegram", user) }]
                  : []),
                ...(available.includes("clearEmailUndeliverable")
                  ? [{ label: t("users.emailUndeliverable.clear"), icon: MailCheck, onClick: () => actions.run("clearEmailUndeliverable", user) }]
                  : []),
                ...(available.includes("unblock")
                  ? [{ label: t("users.unblock.action"), icon: Unlock, onClick: () => actions.run("unblock", user) }]
                  : []),
                ...[
                  ...(available.includes("block")
                    ? [{ label: t("users.block.action"), icon: Lock, onClick: () => actions.run("block", user) }]
                    : []),
                  ...(available.includes("resetReferralCode")
                    ? [
                        {
                          label: t("referrals.stats.resetCode"),
                          icon: RotateCcw,
                          onClick: () => actions.run("resetReferralCode", user),
                        },
                      ]
                    : []),
                  ...(available.includes("merge")
                    ? [{ label: t("users.merge.action"), icon: GitMerge, onClick: () => actions.run("merge", user) }]
                    : []),
                  ...(available.includes("deleteSubscriptions")
                    ? [
                        {
                          label: t("users.deleteSubscriptions.action"),
                          icon: ListX,
                          onClick: () => actions.run("deleteSubscriptions", user),
                        },
                      ]
                    : []),
                  ...(available.includes("delete")
                    ? [{ label: t("common.delete"), icon: Trash2, onClick: () => actions.run("delete", user) }]
                    : []),
                ].map((item, index) => ({ ...item, variant: "danger" as const, separatorBefore: index === 0 })),
              ]}
            />
          </div>
        </div>
      )}
      {actions.dialogs}
      {isGranting && (
        <GrantSubscriptionDialog
          userId={user.id}
          onGranted={() => setSubscriptionsVersion((version) => version + 1)}
          onClose={() => setIsGranting(false)}
        />
      )}
    </>
  );
}
