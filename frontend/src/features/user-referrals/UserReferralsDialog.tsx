import { BarChart3, Coins, User, UserPlus, Users } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getUserReferralStats } from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { userLabel } from "@entities/user/display";
import { OpenUserFooter } from "@features/open-user/OpenUserFooter";
import { InvitedUsersList } from "@features/user-referrals/InvitedUsersList";
import { ReferralOverview } from "@features/user-referrals/ReferralOverview";
import { ReferralRewardsList } from "@features/user-referrals/ReferralRewardsList";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { initials } from "@shared/lib/initials";
import { Badge } from "@shared/ui/Badge";
import { GLASS_DIALOG_BODY_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Modal } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";

type ReferralsTab = "overview" | "invited" | "rewards";

interface UserReferralsDialogProps {
  userId: number;
  userName: string;
  username?: string | null;
  onClose: () => void;
}

export function UserReferralsDialog({ onClose, ...props }: UserReferralsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <UserReferralsDialogBody {...props} />
    </Modal>
  );
}

function UserReferralsDialogBody({
  userId,
  userName,
  username,
}: Omit<UserReferralsDialogProps, "onClose">) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canViewInvited = permissions.includes("REFERRALS_INVITED_VIEW");
  const canViewRewards = permissions.includes("REFERRALS_REWARDS_VIEW");
  const [state] = useAsyncResource((signal) => getUserReferralStats(userId, signal));
  const [tab, setTab] = useState<ReferralsTab>("overview");
  const [contentRef, contentHeight] = useMeasuredHeight();

  const tabs: DialogTabItem<ReferralsTab>[] = [
    { key: "overview", label: t("referrals.dialog.tabs.overview"), icon: BarChart3 },
    ...(canViewInvited ? [{ key: "invited" as const, label: t("referrals.dialog.tabs.invited"), icon: Users }] : []),
    ...(canViewRewards ? [{ key: "rewards" as const, label: t("referrals.dialog.tabs.rewards"), icon: Coins }] : []),
  ];

  const stats = state.kind === "ready" ? state.data : null;
  const code = stats?.referral_code;

  return (
    <>
      <DialogHeader
        glyph={<span className="text-[11px] font-bold">{initials(userName)}</span>}
        title={userName}
        actions={
          stats?.referrer && (
            <Badge borderless tone="accent">
              <UserPlus className="size-3" />
              {userLabel(stats.referrer, stats.referrer.id, t)}
            </Badge>
          )
        }
        subtitle={
          (username || code) && (
            <>
              {username && `@${username}`}
              {username && code && " · "}
              {code && <span className="font-mono">{code}</span>}
            </>
          )
        }
      />

      <div className="px-3 pt-3">
        <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
      </div>

      <div className={GLASS_DIALOG_BODY_CLASS}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {state.kind === "loading" && <Spinner size="card" />}
            {state.kind === "error" && (
              <ErrorState text={t("common.loadError")} />
            )}
            {state.kind === "ready" && (
              <>
                {tab === "overview" && <ReferralOverview userId={userId} stats={state.data} />}
                {tab === "invited" && <InvitedUsersList userId={userId} />}
                {tab === "rewards" && <ReferralRewardsList userId={userId} />}
              </>
            )}
          </div>
        </motion.div>
      </div>

      <OpenUserFooter
        glass
        links={[
          // two side by side: short labels, the long ones wrap
          { label: t("referrals.stats.toReferrer"), icon: UserPlus, user: stats && { id: stats.referrer_id } },
          { label: t("referrals.stats.toUser"), icon: User, user: { id: userId } },
        ]}
      />
    </>
  );
}
