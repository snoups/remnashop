import { AlertCircle, BarChart3, Coins, User, UserPlus, Users } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getUserReferralStats } from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { OpenUserFooter } from "@features/open-user/OpenUserFooter";
import { InvitedUsersList } from "@features/user-referrals/InvitedUsersList";
import { ReferralOverview } from "@features/user-referrals/ReferralOverview";
import { ReferralRewardsList } from "@features/user-referrals/ReferralRewardsList";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { initials } from "@shared/lib/initials";
import { Badge } from "@shared/ui/Badge";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
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
  const [state] = useAsyncResource((signal) => getUserReferralStats(userId, signal));
  const [tab, setTab] = useState<ReferralsTab>("overview");
  const [contentRef, contentHeight] = useMeasuredHeight();

  const tabs: DialogTabItem<ReferralsTab>[] = [
    { key: "overview", label: t("referrals.dialog.tabs.overview"), icon: BarChart3 },
    ...(canViewInvited ? [{ key: "invited" as const, label: t("referrals.dialog.tabs.invited"), icon: Users }] : []),
    { key: "rewards", label: t("referrals.dialog.tabs.rewards"), icon: Coins },
  ];

  const stats = state.kind === "ready" ? state.data : null;
  const code = stats?.referral_code;

  return (
    <>
      <DialogHeader
        glyph={<span className="text-[12px] font-bold">{initials(userName)}</span>}
        title={userName}
        badges={
          stats?.referrer && (
            <Badge tone="accent">
              <UserPlus className="size-3" />
              {stats.referrer.name || t("users.deleted.name")}
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

      <div className="px-4 pb-3 pt-4">
        <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {state.kind === "loading" && <Spinner size="card" />}
            {state.kind === "error" && (
              <div className="flex flex-col items-center gap-2 py-8 text-error">
                <AlertCircle className="size-5" />
                <p className="text-sm">{t("referrals.stats.loadError")}</p>
              </div>
            )}
            {state.kind === "ready" && (
              <>
                {tab === "overview" && <ReferralOverview userId={userId} stats={state.data} />}
                {tab === "invited" && <InvitedUsersList userId={userId} />}
                {tab === "rewards" && <ReferralRewardsList rewards={state.data.rewards} />}
              </>
            )}
          </div>
        </motion.div>
      </div>

      <OpenUserFooter
        links={[
          // two side by side: short labels, the long ones wrap
          { label: t("referrals.stats.toReferrer"), icon: UserPlus, user: stats && { id: stats.referrer_id } },
          { label: t("referrals.stats.toUser"), icon: User, user: { id: userId } },
        ]}
      />
    </>
  );
}
