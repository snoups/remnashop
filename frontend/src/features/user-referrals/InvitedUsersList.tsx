import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { userName } from "@entities/user/display";
import { type InvitedUser, listInvitedUsers } from "@entities/referrals/api";
import { useCanOpenUsers } from "@features/open-user/openable-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { PillTabs } from "@shared/ui/PillTabs";
import { formatRewardAmounts } from "@features/user-referrals/format";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { Spinner } from "@shared/ui/Spinner";
import { UserRow } from "@shared/ui/UserRow";
import { formatDate } from "@shared/lib/relative-time";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 200;
const LEVELS = [1, 2, 3];

export function InvitedUsersList({ userId }: { userId: number }) {
  const { t } = useTranslation();
  const [level, setLevel] = useState<number | undefined>(undefined);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 items-end gap-2">
        <SearchField
          id={`referral-invited-search-${userId}`}
          label={t("referrals.list.search")}
          hideLabel
          compact
          placeholder={t("referrals.dialog.searchPlaceholder")}
          value={searchInput}
          onChange={setSearchInput}
        />
        <div className="min-w-0">
          <PillTabs
            items={[
              { key: "ALL", label: t("referrals.dialog.levelAll") },
              ...LEVELS.map((value) => ({ key: String(value), label: String(value) })),
            ]}
            activeKey={level === undefined ? "ALL" : String(level)}
            onSelect={(key) => setLevel(key === "ALL" ? undefined : Number(key))}
            size="compact"
          />
        </div>
      </div>
      {/* keyed by filters: a change remounts and refetches from page 1 */}
      <InvitedUsersPage key={`${level}-${search}`} userId={userId} level={level} search={search} />
    </div>
  );
}

/** One filtered list, newest first; on its own (no filters) in the user card's Invited tab. */
export function InvitedUsersPage({
  userId,
  level,
  search = "",
}: {
  userId: number;
  level?: number;
  search?: string;
}) {
  const { t, i18n } = useTranslation();
  const { openUser: openUserCard } = useOpenEntity();
  const canOpenUsers = useCanOpenUsers();
  const filters = useMemo(() => ({ level, search: search || undefined, pageSize: PAGE_SIZE }), [level, search]);
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (current: typeof filters, page, signal) => listInvitedUsers(userId, { ...current, page }, signal),
    filters,
  );

  const openUser = (item: InvitedUser) => {
    if (!item.user) return;
    openUserCard(item.user.id);
  };

  const subtitle = (item: InvitedUser) => (
    <>
      {item.via && (
        <>
          {t("referrals.dialog.via", { name: userName(item.via, t) })}{" "}
          <span className="font-mono">#{item.via.id}</span>
          {" · "}
        </>
      )}
      {formatDate(item.created_at, i18n.language)}
    </>
  );

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("referrals.dialog.invitedEmpty")} />
      )}
      {state.kind === "ready" &&
        state.items.map((item, index) => {
          const rewards = formatRewardAmounts(t, item.reward_amounts);
          return (
            <UserRow
              key={item.user?.id ?? `deleted-${index}`}
              name={item.user && userName(item.user, t)}
              id={item.user?.id}
              unnamed={Boolean(item.user && !item.user.name)}
              subtitle={subtitle(item)}
              aside={
                <>
                  <Badge borderless tone={item.level === 1 ? "accent" : "neutral"}>
                    {t("referrals.list.levelBadge", { level: item.level })}
                  </Badge>
                  <span className="flex w-24 shrink-0 flex-col items-end text-[12px] leading-tight tabular-nums">
                    {rewards.length === 0 && <span className="text-muted-foreground">{t("common.none")}</span>}
                    {rewards.map((reward) => (
                      <span key={reward} className="max-w-full truncate font-semibold text-foreground">
                        {reward}
                      </span>
                    ))}
                  </span>
                </>
              }
              onClick={canOpenUsers && item.user ? () => openUser(item) : undefined}
            />
          );
        })}
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
