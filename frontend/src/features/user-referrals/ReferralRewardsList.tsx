import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";

import type { ReferralReward } from "@entities/referrals/api";
import { formatReward, initials, userHandle } from "@features/user-referrals/format";
import { bounceTap } from "@shared/lib/bounceState";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";

const PAGE_SIZE = 10;

export function ReferralRewardsList({ rewards }: { rewards: ReferralReward[] }) {
  const { t, i18n } = useTranslation();
  const { openUser: openUserCard } = useOpenEntity();
  // the whole history arrives with the stats; paged here only to keep the list short
  const [shown, setShown] = useState(PAGE_SIZE);

  const openBuyer = (reward: ReferralReward) => {
    if (!reward.buyer) return;
    openUserCard(reward.buyer.id);
  };

  const subtitle = (reward: ReferralReward): string =>
    [
      reward.buyer ? userHandle(reward.buyer) : null,
      reward.created_at
        ? formatDateTime(reward.created_at, i18n.language)
        : null,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <Card variant="list">
      {rewards.length === 0 && <EmptyState text={t("referrals.stats.rewardsEmpty")} />}
      {rewards.slice(0, shown).map((reward, index) => (
        <motion.button
          key={index}
          type="button"
          disabled={!reward.buyer}
          onClick={() => openBuyer(reward)}
          {...bounceTap(0.03)}
          className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors enabled:hover:bg-white/[0.04]"
        >
          <span
            className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground"
          >
            {reward.buyer?.name ? initials(reward.buyer.name) : "?"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">
              {reward.buyer?.name || t("referrals.dialog.deletedUser")}
            </p>
            <p className="truncate text-[11.5px] leading-tight text-muted-foreground">{subtitle(reward)}</p>
          </div>
          {reward.level && (
            <Badge tone={reward.level === 1 ? "accent" : "neutral"}>
              {t("referrals.list.levelBadge", { level: reward.level })}
            </Badge>
          )}
          <span className="w-24 shrink-0 truncate text-right text-[12.5px] font-semibold tabular-nums text-foreground">
            +{formatReward(t, reward.type, reward.amount)}
          </span>
        </motion.button>
      ))}
      {shown < rewards.length && (
        <div className="px-2.5 py-1">
          <LoadMoreButton onClick={() => setShown(shown + PAGE_SIZE)} shown={shown} total={rewards.length} />
        </div>
      )}
    </Card>
  );
}
