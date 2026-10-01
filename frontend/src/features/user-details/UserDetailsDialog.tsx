import {
  BarChart3,
  CreditCard,
  Gift,
  History,
  Lock,
  MonitorSmartphone,
  Receipt,
  Ticket,
  Trash2,
  Unlock,
  User,
} from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ROLE_BADGE_TONE } from "@entities/admin/display";
import type { UserListItem } from "@entities/user/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import {
  AnalyticsTab,
  PromocodesTab,
  ReferralsTab,
  SubscriptionsTab,
  TransactionsTab,
} from "@features/user-details/UserActivityTabs";
import { EventsTab, ProfileTab, SessionsTab } from "@features/user-details/UserDetailsTabs";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import type { Permission } from "@shared/types/rbac";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

export type UserDetailsFollowUp = "block" | "unblock" | "delete";

type UserDetailsTab =
  | "profile"
  | "analytics"
  | "transactions"
  | "subscriptions"
  | "promocodes"
  | "referrals"
  | "sessions"
  | "events";

interface UserDetailsDialogProps {
  user: UserListItem;
  /** footer actions the caller allows; none renders no footer */
  followUps?: UserDetailsFollowUp[];
  /** Fires after the exit animation; `followUp` is the action picked in the footer, if any. */
  onClose: (followUp?: UserDetailsFollowUp) => void;
}

function getInitials(user: UserListItem): string {
  return (user.login ?? user.name).slice(0, 2).toUpperCase();
}

function getHandle(user: UserListItem): string | null {
  if (user.username) return `@${user.username}`;
  return user.login ?? user.email;
}

export function UserDetailsDialog({ user, followUps = [], onClose }: UserDetailsDialogProps) {
  // the footer action opens its own modal only once this one has animated out
  const followUpRef = useRef<UserDetailsFollowUp | undefined>(undefined);

  return (
    <Modal onClose={() => onClose(followUpRef.current)} size="lg" scrollable>
      <UserDetailsDialogBody
        user={user}
        followUps={followUps}
        onFollowUp={(followUp) => {
          followUpRef.current = followUp;
        }}
      />
    </Modal>
  );
}

function UserDetailsDialogBody({
  user,
  followUps,
  onFollowUp,
}: {
  user: UserListItem;
  followUps: UserDetailsFollowUp[];
  onFollowUp: (followUp: UserDetailsFollowUp) => void;
}) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [tab, setTab] = useState<UserDetailsTab>("profile");
  const [contentRef, contentHeight] = useMeasuredHeight();
  const currentUserState = useCurrentUser();
  const permissions = currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  // the per-user session endpoints reject yourself (see UserSessionsDialog)
  const isSelf = currentUserState.kind === "ready" && currentUserState.data.id === user.id;
  const isDeleted = Boolean(user.deleted_at);
  const handle = isDeleted ? `#${user.id}` : getHandle(user);

  const hasAny = (...required: Permission[]) => required.some((permission) => permissions.includes(permission));
  const tabs: DialogTabItem<UserDetailsTab>[] = [
    { key: "profile", label: t("admins.details.tabs.profile"), icon: User },
    ...(hasAny("TRANSACTIONS_VIEW", "TRANSACTIONS_SUMMARY_VIEW", "REFERRALS_VIEW")
      ? [{ key: "analytics" as const, label: t("users.details.tabs.analytics"), icon: BarChart3 }]
      : []),
    ...(hasAny("TRANSACTIONS_VIEW")
      ? [{ key: "transactions" as const, label: t("users.details.tabs.transactions"), icon: Receipt }]
      : []),
    ...(hasAny("SUBSCRIPTIONS_VIEW")
      ? [{ key: "subscriptions" as const, label: t("users.details.tabs.subscriptions"), icon: CreditCard }]
      : []),
    ...(hasAny("PROMOCODES_ACTIVATIONS_VIEW")
      ? [{ key: "promocodes" as const, label: t("users.details.tabs.promocodes"), icon: Ticket }]
      : []),
    ...(hasAny("REFERRALS_VIEW")
      ? [{ key: "referrals" as const, label: t("users.details.tabs.referrals"), icon: Gift }]
      : []),
    ...(permissions.includes("USER_SESSIONS_VIEW") && !isSelf && !isDeleted
      ? [{ key: "sessions" as const, label: t("admins.details.tabs.sessions"), icon: MonitorSmartphone }]
      : []),
    ...(permissions.includes("EVENT_LOG_VIEW")
      ? [{ key: "events" as const, label: t("admins.details.tabs.events"), icon: History }]
      : []),
  ];

  const closeWith = (followUp: UserDetailsFollowUp) => {
    onFollowUp(followUp);
    close();
  };

  return (
    <>
      <DialogHeader
        glyph={
          isDeleted ? (
            <Trash2 className="size-4" />
          ) : (
            <span className="text-[11px] font-bold">{getInitials(user)}</span>
          )
        }
        tone={user.is_blocked && !isDeleted ? "danger" : "glass"}
        title={isDeleted ? t("users.deleted.name") : user.name}
        badges={
          <>
            {user.role !== "USER" && <Badge tone={ROLE_BADGE_TONE[user.role]}>{t(`roles.${user.role}`)}</Badge>}
            {isDeleted && <Badge tone="neutral">{t("users.deleted.badge")}</Badge>}
            {user.is_blocked && !isDeleted && <Badge tone="error">{t("users.status.blocked")}</Badge>}
          </>
        }
        subtitle={handle && <span className="font-mono">{handle}</span>}
      />

      {tabs.length > 1 && (
        <div className="px-4 pb-3 pt-4">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={`min-h-0 flex-1 overflow-y-auto px-4 pb-4 ${tabs.length > 1 ? "" : "pt-4"}`}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "profile" && <ProfileTab user={user} />}
            {tab === "analytics" && <AnalyticsTab userId={user.id} />}
            {tab === "transactions" && <TransactionsTab userId={user.id} />}
            {tab === "subscriptions" && <SubscriptionsTab userId={user.id} />}
            {tab === "promocodes" && <PromocodesTab userId={user.id} />}
            {tab === "referrals" && <ReferralsTab userId={user.id} readOnly={isDeleted} />}
            {tab === "sessions" && <SessionsTab userId={user.id} />}
            {tab === "events" && <EventsTab actorId={user.id} />}
          </div>
        </motion.div>
      </div>

      {/* a deleted account is read-only */}
      {followUps.length > 0 && !isDeleted && (
        <div className="flex items-center gap-2 border-t border-white/[0.07] px-5 py-4">
          {followUps.includes("delete") && (
            <Button variant="danger" onClick={() => closeWith("delete")}>
              <Trash2 className="size-3.5" />
              {t("users.delete.action")}
            </Button>
          )}
          {followUps.includes("block") && (
            <Button variant="secondary" className="ml-auto" onClick={() => closeWith("block")}>
              <Lock className="size-3.5" />
              {t("users.block.action")}
            </Button>
          )}
          {followUps.includes("unblock") && (
            <Button variant="secondary" className="ml-auto" onClick={() => closeWith("unblock")}>
              <Unlock className="size-3.5" />
              {t("users.unblock.action")}
            </Button>
          )}
        </div>
      )}
    </>
  );
}
