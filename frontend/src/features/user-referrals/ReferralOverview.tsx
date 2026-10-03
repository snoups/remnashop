import { Gift, Hash, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getUserReferralRevenue, type ReferralStats } from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { REWARD_TYPES, formatReward, userHandle } from "@features/user-referrals/format";
import { formatMoney } from "@shared/lib/format";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";

export function ReferralOverview({ userId, stats }: { userId: number; stats: ReferralStats }) {
  return (
    <div className="flex flex-col gap-3">
      <ReferralKpis userId={userId} stats={stats} />
      <ReferralProgramCard stats={stats} />
    </div>
  );
}

export function ReferralKpis({ userId, stats }: { userId: number; stats: ReferralStats }) {
  const { t, i18n } = useTranslation();
  const canViewRevenue = usePermissions().includes("REFERRALS_REVENUE_VIEW");
  const [revenueState] = useAsyncResource((signal) =>
    canViewRevenue ? getUserReferralRevenue(userId, signal) : Promise.resolve(null),
  );
  const revenue = revenueState.kind === "ready" ? revenueState.data : null;
  const none = t("common.none");

  const levels = Object.entries(stats.counts_by_level).sort(([a], [b]) => Number(a) - Number(b));
  const invited = levels.reduce((sum, [, count]) => sum + count, 0);
  const rewardSums = REWARD_TYPES.flatMap((type) => {
    const total = stats.rewards.filter((r) => r.type === type).reduce((sum, r) => sum + Number(r.amount), 0);
    return total ? [formatReward(t, type, total)] : [];
  });

  return (
    <div className={`grid gap-3 ${canViewRevenue ? "grid-cols-3" : "grid-cols-2"}`}>
      <KpiTile
        label={t("referrals.dialog.invited")}
        value={String(invited)}
        hint={levels.length ? levels.map(([level, count]) => `${t("referrals.list.levelBadge", { level })}: ${count}`).join(" · ") : undefined}
      />
      <KpiTile
        label={t("referrals.dialog.rewardsCount")}
        value={String(stats.rewards.length)}
        hint={rewardSums.length ? rewardSums.join(" · ") : undefined}
      />
      {canViewRevenue && (
        <KpiTile
          label={t("referrals.dialog.revenue")}
          value={revenue ? formatMoney(revenue.amount, revenue.currency, i18n.language) : none}
          hint={revenue ? t("referrals.dialog.payingCount", { paid: revenue.paying_count, total: invited }) : undefined}
        />
      )}
    </div>
  );
}

export function ReferralProgramCard({ stats, showCode = true }: { stats: ReferralStats; showCode?: boolean }) {
  const { t } = useTranslation();
  const none = t("common.none");

  return (
    <Card variant="list" title={t("referrals.dialog.program")} icon={Gift}>
      {showCode && (
        <InfoRow icon={Hash} label={t("referrals.stats.referralCodeLabel")} copyValue={stats.referral_code ?? undefined} mono>
          {stats.referral_code ?? none}
        </InfoRow>
      )}
      <InfoRow icon={UserPlus} label={t("referrals.stats.referrerLabel")}>
        {stats.referrer ? (
          <span className="truncate">
            {stats.referrer.name || t("users.deleted.name")}{" "}
            <span className="font-mono font-medium text-muted-foreground">{userHandle(stats.referrer)}</span>
          </span>
        ) : stats.referrer_id !== null ? (
          `#${stats.referrer_id}`
        ) : (
          none
        )}
      </InfoRow>
    </Card>
  );
}
