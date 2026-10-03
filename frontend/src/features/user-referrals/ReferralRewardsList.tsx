import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";

import type { ReferralReward } from "@entities/referrals/api";
import { formatReward, userHandle } from "@features/user-referrals/format";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { UserRow } from "@shared/ui/UserRow";

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
        <UserRow
          key={index}
          name={reward.buyer?.name}
          subtitle={subtitle(reward)}
          aside={
            <>
              {reward.level && (
                <Badge tone={reward.level === 1 ? "accent" : "neutral"}>
                  {t("referrals.list.levelBadge", { level: reward.level })}
                </Badge>
              )}
              <span className="w-24 shrink-0 truncate text-right text-[12.5px] font-semibold tabular-nums text-foreground">
                +{formatReward(t, reward.type, reward.amount)}
              </span>
            </>
          }
          onClick={reward.buyer ? () => openBuyer(reward) : undefined}
        />
      ))}
      {shown < rewards.length && (
        <div className="px-2.5 py-1">
          <LoadMoreButton onClick={() => setShown(shown + PAGE_SIZE)} shown={shown} total={rewards.length} />
        </div>
      )}
    </Card>
  );
}
