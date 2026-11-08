import { Hash, Share2, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getUserReferralRevenue, type ReferralStats } from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { userContacts, userName } from "@entities/user/display";
import { REWARD_TYPES, formatReward } from "@features/user-referrals/format";
import { formatMoney } from "@shared/lib/format";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { FieldHint } from "@shared/ui/FieldHint";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { Tag } from "@shared/ui/Tag";

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
    const total = stats.reward_amounts[type];
    return total ? [formatReward(t, type, total)] : [];
  });

  return (
    <div className={`grid gap-3 ${canViewRevenue ? "grid-cols-3" : "grid-cols-2"}`}>
      <KpiTile
        glass
        label={t("referrals.dialog.invited")}
        value={String(invited)}
        hint={
          levels.length ? (
            <span className="flex flex-wrap gap-x-3 gap-y-1">
              {levels.map(([level, count]) => {
                const hint = t("referrals.list.levelHint", { level, count });
                return (
                  <FieldHint
                    key={level}
                    text={hint}
                    trigger={
                      <Tag className="cursor-help">
                        {level} · {count}
                      </Tag>
                    }
                  />
                );
              })}
            </span>
          ) : undefined
        }
      />
      <KpiTile
        glass
        label={t("referrals.dialog.rewardsCount")}
        value={String(stats.reward_count)}
        hint={rewardSums.length ? rewardSums.join(" · ") : undefined}
      />
      {canViewRevenue && (
        <KpiTile
          glass
          label={t("referrals.dialog.revenue")}
          value={revenue ? formatMoney(revenue.amount, revenue.currency, i18n.language) : none}
          hint={revenue && invited > 0 ? t("referrals.dialog.payingCount", { paid: revenue.paying_count, total: invited }) : undefined}
        />
      )}
    </div>
  );
}

function ReferralProgramCard({ stats }: { stats: ReferralStats }) {
  const { t } = useTranslation();
  const none = t("common.none");

  return (
    <DialogCard title={t("referrals.dialog.program")} icon={Share2}>
      <InfoRow icon={Hash} label={t("referrals.stats.referralCodeLabel")} copyValue={stats.referral_code ?? undefined} mono>
        {stats.referral_code ?? none}
      </InfoRow>
      <InfoRow icon={UserPlus} label={t("referrals.stats.referrerLabel")}>
        {stats.referrer ? (
          <>
            <span className="truncate">{userName(stats.referrer, t)}</span>
            <span className="shrink-0 font-mono font-medium text-muted-foreground">#{stats.referrer.id}</span>
            {userContacts(stats.referrer, t) && (
              <span className="truncate font-medium text-muted-foreground">· {userContacts(stats.referrer, t)}</span>
            )}
          </>
        ) : stats.referrer_id !== null ? (
          `#${stats.referrer_id}`
        ) : (
          none
        )}
      </InfoRow>
    </DialogCard>
  );
}
