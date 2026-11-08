import { useTranslation } from "react-i18next";
import { userName } from "@entities/user/display";
import { useCanOpenUsers } from "@features/open-user/openable-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";

import { type ReferralReward, listUserReferralRewards } from "@entities/referrals/api";
import { formatReward } from "@features/user-referrals/format";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { UserRow } from "@shared/ui/UserRow";

const PAGE_SIZE = 10;

export function ReferralRewardsList({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const { openUser: openUserCard } = useOpenEntity();
  const canOpenUsers = useCanOpenUsers();
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, page, signal) => listUserReferralRewards(id, page, PAGE_SIZE, signal),
    userId,
  );

  const openBuyer = (reward: ReferralReward) => {
    if (!reward.buyer) return;
    openUserCard(reward.buyer.id);
  };

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && <EmptyState text={t("referrals.stats.rewardsEmpty")} />}
      {state.kind === "ready" &&
        state.items.map((reward, index) => (
          <UserRow
            key={index}
            name={reward.buyer && userName(reward.buyer, t)}
            id={reward.buyer?.id}
            unnamed={Boolean(reward.buyer && !reward.buyer.name)}
            subtitle={formatDateTime(reward.created_at, i18n.language)}
            aside={
              <>
                {reward.level && (
                  <Badge borderless tone={reward.level === 1 ? "accent" : "neutral"}>
                    {t("referrals.list.levelBadge", { level: reward.level })}
                  </Badge>
                )}
                <span className="w-24 shrink-0 truncate text-right text-[12px] font-semibold tabular-nums text-foreground">
                  +{formatReward(t, reward.type, reward.amount)}
                </span>
              </>
            }
            onClick={canOpenUsers && reward.buyer ? () => openBuyer(reward) : undefined}
          />
        ))}
      {state.kind === "ready" && hasMore && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void loadMore()}
            isLoading={isLoadingMore}
            shown={state.items.length}
            total={state.total}
          />
        </div>
      )}
    </DialogCard>
  );
}
